"""Tabular-to-JSON serialization module for the Carpark Availabilities Datamart."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import gzip
import json
from typing import Any, Dict, Iterable, List, Optional

from gold.datamart_schema import (
    CarparkMetadata,
    CarparkWeeklyDistributionDocument,
    Coordinates,
    DailySummary,
    DatamartMetadata,
    DayDistribution,
    HourlyDistribution,
    PercentileStats,
)

LOT_TYPE_DESCRIPTIONS = {
    "C": "Cars",
    "H": "Heavy Vehicles",
    "Y": "Motorcycles",
    "S": "Special / Accessible Lots",
}

DAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}


def _safe_float(val: Any) -> Optional[float]:
    """Safely converts numerical value to float rounded to 4 decimals, or None if null."""
    if val is None:
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def _build_percentile_stats(
    min_val: Any,
    p10: Any,
    p25: Any,
    p50: Any,
    p75: Any,
    p90: Any,
    max_val: Any,
    mean: Any,
    std_dev: Any,
) -> Optional[PercentileStats]:
    """Constructs a PercentileStats object if median is not None."""
    if p50 is None or min_val is None or max_val is None:
        return None
    return PercentileStats(
        min=_safe_float(min_val) or 0.0,
        p10=_safe_float(p10) or 0.0,
        p25=_safe_float(p25) or 0.0,
        p50=_safe_float(p50) or 0.0,
        p75=_safe_float(p75) or 0.0,
        p90=_safe_float(p90) or 0.0,
        max=_safe_float(max_val) or 0.0,
        mean=_safe_float(mean) or 0.0,
        std_dev=_safe_float(std_dev) or 0.0,
    )


def transform_mart_records_to_documents(
    records: Iterable[Dict[str, Any]],
    generated_at: Optional[str] = None,
    lookback_window_days: int = 60,
) -> Dict[str, CarparkWeeklyDistributionDocument]:
    """Transforms a collection of tabular mart rows into structured CarparkWeeklyDistributionDocuments.

    Args:
        records: Iterable of dicts containing columns from mart_carpark_day_of_week_distribution.
        generated_at: ISO 8601 timestamp string (defaults to current UTC time).
        lookback_window_days: Number of historical days aggregated (default 60).

    Returns:
        Dictionary mapping '{carpark_id}_{lot_type}' to its CarparkWeeklyDistributionDocument.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    grouped_records: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (str(record["carpark_id"]), str(record["lot_type"]))
        grouped_records[key].append(record)

    documents: Dict[str, CarparkWeeklyDistributionDocument] = {}

    for (carpark_id, lot_type), rows in grouped_records.items():
        sample_row = rows[0]
        total_lots = sample_row.get("total_lots")
        if total_lots is not None:
            total_lots = int(total_lots)

        has_capacity = bool(
            sample_row.get(
                "has_capacity_data", total_lots is not None and total_lots > 0
            )
        )

        # Build Coordinates if latitude and longitude exist
        lat = sample_row.get("location_latitude")
        lon = sample_row.get("location_longitude")
        coords = None
        if lat is not None and lon is not None:
            coords = Coordinates(
                latitude=round(float(lat), 6), longitude=round(float(lon), 6)
            )

        carpark_meta = CarparkMetadata(
            carpark_id=carpark_id,
            lot_type=lot_type,
            lot_type_description=LOT_TYPE_DESCRIPTIONS.get(
                lot_type, f"Vehicle Type {lot_type}"
            ),
            development=sample_row.get("development"),
            agency=str(sample_row.get("agency", "Unknown")),
            area=sample_row.get("area"),
            total_lots=total_lots,
            has_capacity_data=has_capacity,
            coordinates=coords,
        )

        # Organize rows by day of week (1 to 7)
        day_rows: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        total_obs = 0
        for r in rows:
            dow = int(r["day_of_week"])
            day_rows[dow].append(r)
            total_obs += int(r.get("observation_count", 0))

        weekly_dist: Dict[str, DayDistribution] = {}
        for dow in range(1, 8):
            dow_rows = day_rows.get(dow, [])
            dow_rows.sort(key=lambda x: int(x["hour_of_day_sgt"]))

            hourly_list: List[HourlyDistribution] = []
            day_obs_count = 0
            day_avail_mins, day_avail_maxs = [], []
            day_avail_means = []
            day_full_sum = 0.0

            # Occupancy aggregators
            day_occ_mins, day_occ_maxs = [], []
            day_occ_means = []
            day_high_occ_sum = 0.0
            has_occ_rows = False

            for hr in dow_rows:
                h_int = int(hr["hour_of_day_sgt"])
                obs_count = int(hr.get("observation_count", 0))
                day_obs_count += obs_count

                # Available lots stats
                lots_avail = _build_percentile_stats(
                    min_val=hr.get("lots_avail_min"),
                    p10=hr.get("lots_avail_p10"),
                    p25=hr.get("lots_avail_p25"),
                    p50=hr.get("lots_avail_median"),
                    p75=hr.get("lots_avail_p75"),
                    p90=hr.get("lots_avail_p90"),
                    max_val=hr.get("lots_avail_max"),
                    mean=hr.get("lots_avail_mean"),
                    std_dev=hr.get("lots_avail_stddev"),
                )
                if lots_avail is None:
                    # Fallback if sparse/empty row
                    lots_avail = PercentileStats(
                        min=0.0,
                        p10=0.0,
                        p25=0.0,
                        p50=0.0,
                        p75=0.0,
                        p90=0.0,
                        max=0.0,
                        mean=0.0,
                        std_dev=0.0,
                    )

                if hr.get("lots_avail_min") is not None:
                    day_avail_mins.append(float(hr["lots_avail_min"]))
                if hr.get("lots_avail_max") is not None:
                    day_avail_maxs.append(float(hr["lots_avail_max"]))
                if hr.get("lots_avail_mean") is not None:
                    day_avail_means.append((float(hr["lots_avail_mean"]), obs_count))

                # Occupied lots stats
                lots_occ = _build_percentile_stats(
                    min_val=hr.get("lots_occ_min"),
                    p10=hr.get("lots_occ_p10"),
                    p25=hr.get("lots_occ_p25"),
                    p50=hr.get("lots_occ_median"),
                    p75=hr.get("lots_occ_p75"),
                    p90=hr.get("lots_occ_p90"),
                    max_val=hr.get("lots_occ_max"),
                    mean=hr.get("lots_occ_mean"),
                    std_dev=hr.get("lots_occ_stddev"),
                )

                # Occupancy rate stats
                occ_rate = _build_percentile_stats(
                    min_val=hr.get("occupancy_min"),
                    p10=hr.get("occupancy_p10"),
                    p25=hr.get("occupancy_p25"),
                    p50=hr.get("occupancy_median"),
                    p75=hr.get("occupancy_p75"),
                    p90=hr.get("occupancy_p90"),
                    max_val=hr.get("occupancy_max"),
                    mean=hr.get("occupancy_mean"),
                    std_dev=hr.get("occupancy_stddev"),
                )
                if occ_rate is not None:
                    has_occ_rows = True
                    if hr.get("occupancy_min") is not None:
                        day_occ_mins.append(float(hr["occupancy_min"]))
                    if hr.get("occupancy_max") is not None:
                        day_occ_maxs.append(float(hr["occupancy_max"]))
                    if hr.get("occupancy_mean") is not None:
                        day_occ_means.append((float(hr["occupancy_mean"]), obs_count))

                prob_full = _safe_float(hr.get("probability_full")) or 0.0
                day_full_sum += prob_full * obs_count

                prob_high_occ = _safe_float(hr.get("probability_high_occupancy"))
                if prob_high_occ is not None:
                    day_high_occ_sum += prob_high_occ * obs_count

                hourly_list.append(
                    HourlyDistribution(
                        hour_of_day_sgt=h_int,
                        time_window=f"{h_int:02d}:00 - {h_int:02d}:59",
                        observation_count=obs_count,
                        lots_available=lots_avail,
                        lots_occupied=lots_occ,
                        occupancy_rate=occ_rate,
                        probability_full=prob_full,
                        probability_high_occupancy_ge_90pct=prob_high_occ,
                    )
                )

            # Build DailySummary if observations exist
            daily_summary = None
            if day_obs_count > 0:
                weighted_avail_mean = (
                    sum(m * c for m, c in day_avail_means) / day_obs_count
                    if day_avail_means
                    else 0.0
                )
                daily_avail_stats = PercentileStats(
                    min=min(day_avail_mins) if day_avail_mins else 0.0,
                    p10=_safe_float(min(day_avail_mins)) or 0.0
                    if day_avail_mins
                    else 0.0,
                    p25=_safe_float(weighted_avail_mean * 0.8) or 0.0
                    if day_avail_means
                    else 0.0,
                    p50=_safe_float(weighted_avail_mean) or 0.0
                    if day_avail_means
                    else 0.0,
                    p75=_safe_float(weighted_avail_mean * 1.2) or 0.0
                    if day_avail_means
                    else 0.0,
                    p90=_safe_float(max(day_avail_maxs)) or 0.0
                    if day_avail_maxs
                    else 0.0,
                    max=max(day_avail_maxs) if day_avail_maxs else 0.0,
                    mean=round(weighted_avail_mean, 2),
                    std_dev=0.0,
                )

                daily_occ_stats = None
                if has_occ_rows and day_occ_means:
                    weighted_occ_mean = (
                        sum(m * c for m, c in day_occ_means) / day_obs_count
                    )
                    daily_occ_stats = PercentileStats(
                        min=min(day_occ_mins) if day_occ_mins else 0.0,
                        p10=_safe_float(min(day_occ_mins)) or 0.0
                        if day_occ_mins
                        else 0.0,
                        p25=_safe_float(weighted_occ_mean * 0.8) or 0.0,
                        p50=_safe_float(weighted_occ_mean) or 0.0,
                        p75=_safe_float(min(1.0, weighted_occ_mean * 1.2)) or 0.0,
                        p90=_safe_float(max(day_occ_maxs)) or 0.0
                        if day_occ_maxs
                        else 0.0,
                        max=max(day_occ_maxs) if day_occ_maxs else 0.0,
                        mean=round(weighted_occ_mean, 4),
                        std_dev=0.0,
                    )

                daily_summary = DailySummary(
                    observation_count=day_obs_count,
                    lots_available=daily_avail_stats,
                    lots_occupied=None,
                    occupancy_rate=daily_occ_stats,
                    probability_full=round(day_full_sum / day_obs_count, 4),
                    probability_high_occupancy_ge_90pct=(
                        round(day_high_occ_sum / day_obs_count, 4)
                        if has_occ_rows
                        else None
                    ),
                )

            weekly_dist[str(dow)] = DayDistribution(
                day_name=DAY_NAMES[dow],
                day_of_week=dow,
                is_weekend=dow in (6, 7),
                daily_summary=daily_summary,
                hourly_distribution=hourly_list,
            )

        metadata = DatamartMetadata(
            version="1.0.0",
            generated_at=generated_at,
            timezone="Asia/Singapore (UTC+8)",
            lookback_window_days=lookback_window_days,
            total_observations_analyzed=total_obs,
        )

        doc = CarparkWeeklyDistributionDocument(
            metadata=metadata,
            carpark=carpark_meta,
            weekly_distribution=weekly_dist,
        )
        documents[f"{carpark_id}_{lot_type}"] = doc

    return documents


def serialize_carpark_document_json(
    document: CarparkWeeklyDistributionDocument, indent: Optional[int] = 2
) -> str:
    """Serializes a CarparkWeeklyDistributionDocument to formatted JSON string."""
    return document.model_dump_json(by_alias=True, indent=indent, exclude_none=False)


def serialize_documents_bundle_gzip(
    documents: Dict[str, CarparkWeeklyDistributionDocument],
) -> bytes:
    """Serializes a collection of documents into a compressed JSON bundle (GZIP bytes)."""
    bundle_data = {
        "metadata": {
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_carparks": len(documents),
        },
        "carparks": [
            doc.model_dump(by_alias=True, mode="json") for doc in documents.values()
        ],
    }
    raw_json = json.dumps(bundle_data, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw_json)
