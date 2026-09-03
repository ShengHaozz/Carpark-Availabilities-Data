"""Tabular-to-JSON serialization module for the Carpark Availabilities Datamart."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import gzip
import json
from typing import Any, Dict, List, Optional

from datamart.schema import (
    DATAMART_SCHEMA_VERSION,
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
    if val is None or val == "" or str(val).lower() == "null":
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
    """Constructs a PercentileStats object if median and bounds are present."""
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


def _build_carpark_metadata(
    carpark_id: str, lot_type: str, sample_row: Dict[str, Any]
) -> CarparkMetadata:
    """Builds CarparkMetadata object from a sample row."""
    total_lots = sample_row.get("total_lots")
    if total_lots is not None and total_lots != "":
        try:
            total_lots = int(total_lots)
        except (ValueError, TypeError):
            total_lots = None
    else:
        total_lots = None

    has_capacity = bool(
        sample_row.get(
            "has_capacity_data", total_lots is not None and total_lots > 0
        )
    )

    lat = sample_row.get("location_latitude")
    lon = sample_row.get("location_longitude")
    coords = None
    if lat is not None and lon is not None and lat != "" and lon != "":
        try:
            coords = Coordinates(
                latitude=round(float(lat), 6), longitude=round(float(lon), 6)
            )
        except (ValueError, TypeError):
            coords = None

    return CarparkMetadata(
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


def _build_hourly_distribution(hr: Dict[str, Any]) -> HourlyDistribution:
    """Constructs HourlyDistribution from a single hourly mart row."""
    h_int = int(hr["hour_of_day_sgt"])
    obs_count = int(hr.get("observation_count", 0))

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

    prob_full = _safe_float(hr.get("probability_full")) or 0.0
    prob_high_occ = _safe_float(hr.get("probability_high_occupancy"))

    return HourlyDistribution(
        hour_of_day_sgt=h_int,
        time_window=f"{h_int:02d}:00 - {h_int:02d}:59",
        observation_count=obs_count,
        lots_available=lots_avail,
        lots_occupied=lots_occ,
        occupancy_rate=occ_rate,
        probability_full=prob_full,
        probability_high_occupancy_ge_90pct=prob_high_occ,
    )


def _build_daily_summary(dow_rows: List[Dict[str, Any]]) -> Optional[DailySummary]:
    """Computes full-day aggregated summary from a list of hourly rows for that day."""
    if not dow_rows:
        return None

    day_obs_count = 0
    day_avail_mins: List[float] = []
    day_avail_maxs: List[float] = []
    day_avail_means: List[tuple[float, int]] = []
    day_full_sum = 0.0

    day_occ_mins: List[float] = []
    day_occ_maxs: List[float] = []
    day_occ_means: List[tuple[float, int]] = []
    day_high_occ_sum = 0.0
    has_occ_rows = False

    for hr in dow_rows:
        obs_count = int(hr.get("observation_count", 0))
        day_obs_count += obs_count

        if hr.get("lots_avail_min") is not None:
            day_avail_mins.append(float(hr["lots_avail_min"]))
        if hr.get("lots_avail_max") is not None:
            day_avail_maxs.append(float(hr["lots_avail_max"]))
        if hr.get("lots_avail_mean") is not None:
            day_avail_means.append((float(hr["lots_avail_mean"]), obs_count))

        if hr.get("occupancy_median") is not None:
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

    if day_obs_count == 0:
        return None

    weighted_avail_mean = (
        sum(m * c for m, c in day_avail_means) / day_obs_count
        if day_avail_means
        else 0.0
    )
    daily_avail_stats = PercentileStats(
        min=min(day_avail_mins) if day_avail_mins else 0.0,
        p10=_safe_float(min(day_avail_mins)) or 0.0 if day_avail_mins else 0.0,
        p25=_safe_float(weighted_avail_mean * 0.8) or 0.0 if day_avail_means else 0.0,
        p50=_safe_float(weighted_avail_mean) or 0.0 if day_avail_means else 0.0,
        p75=_safe_float(weighted_avail_mean * 1.2) or 0.0 if day_avail_means else 0.0,
        p90=_safe_float(max(day_avail_maxs)) or 0.0 if day_avail_maxs else 0.0,
        max=max(day_avail_maxs) if day_avail_maxs else 0.0,
        mean=round(weighted_avail_mean, 2),
        std_dev=0.0,
    )

    daily_occ_stats = None
    if has_occ_rows and day_occ_means:
        weighted_occ_mean = sum(m * c for m, c in day_occ_means) / day_obs_count
        daily_occ_stats = PercentileStats(
            min=min(day_occ_mins) if day_occ_mins else 0.0,
            p10=_safe_float(min(day_occ_mins)) or 0.0 if day_occ_mins else 0.0,
            p25=_safe_float(weighted_occ_mean * 0.8) or 0.0,
            p50=_safe_float(weighted_occ_mean) or 0.0,
            p75=_safe_float(min(1.0, weighted_occ_mean * 1.2)) or 0.0,
            p90=_safe_float(max(day_occ_maxs)) or 0.0 if day_occ_maxs else 0.0,
            max=max(day_occ_maxs) if day_occ_maxs else 0.0,
            mean=round(weighted_occ_mean, 4),
            std_dev=0.0,
        )

    return DailySummary(
        observation_count=day_obs_count,
        lots_available=daily_avail_stats,
        lots_occupied=None,
        occupancy_rate=daily_occ_stats,
        probability_full=round(day_full_sum / day_obs_count, 4),
        probability_high_occupancy_ge_90pct=(
            round(day_high_occ_sum / day_obs_count, 4) if has_occ_rows else None
        ),
    )


def _build_day_distribution(
    dow: int, dow_rows: List[Dict[str, Any]]
) -> DayDistribution:
    """Builds the DayDistribution structure containing hourly slots and daily summary for a day of week."""
    sorted_rows = sorted(dow_rows, key=lambda x: int(x["hour_of_day_sgt"]))
    hourly_list = [_build_hourly_distribution(hr) for hr in sorted_rows]
    daily_summary = _build_daily_summary(sorted_rows)

    return DayDistribution(
        day_name=DAY_NAMES[dow],
        day_of_week=dow,
        is_weekend=dow in (6, 7),
        daily_summary=daily_summary,
        hourly_distribution=hourly_list,
    )


def build_carpark_document(
    carpark_id: str,
    lot_type: str,
    rows: List[Dict[str, Any]],
    generated_at: str,
    lookback_window_days: int = 60,
) -> CarparkWeeklyDistributionDocument:
    """Transforms the collection of rows for a single carpark and lot type into a CarparkWeeklyDistributionDocument."""
    sample_row = rows[0] if rows else {}
    carpark_meta = _build_carpark_metadata(carpark_id, lot_type, sample_row)

    day_rows: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    total_obs = 0
    for r in rows:
        dow = int(r["day_of_week"])
        day_rows[dow].append(r)
        total_obs += int(r.get("observation_count", 0))

    weekly_dist = {
        dow: _build_day_distribution(dow, day_rows.get(dow, [])) for dow in range(1, 8)
    }

    metadata = DatamartMetadata(
        version=DATAMART_SCHEMA_VERSION,
        generated_at=generated_at,
        timezone="Asia/Singapore (UTC+8)",
        lookback_window_days=lookback_window_days,
        total_observations_analyzed=total_obs,
    )

    return CarparkWeeklyDistributionDocument(
        metadata=metadata,
        carpark=carpark_meta,
        weekly_distribution=weekly_dist,
    )


def build_carpark_documents(
    records: List[Dict[str, Any]],
    generated_at: Optional[str] = None,
    lookback_window_days: int = 60,
) -> List[CarparkWeeklyDistributionDocument]:
    """Transforms query records into a list of CarparkWeeklyDistributionDocuments."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    grouped: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (str(record["carpark_id"]), str(record["lot_type"]))
        grouped[key].append(record)

    return [
        build_carpark_document(
            carpark_id=carpark_id,
            lot_type=lot_type,
            rows=rows,
            generated_at=generated_at,
            lookback_window_days=lookback_window_days,
        )
        for (carpark_id, lot_type), rows in grouped.items()
    ]


def dump_carpark_document_json(
    document: CarparkWeeklyDistributionDocument,
    indent: Optional[int] = 2,
) -> str:
    """Serializes a CarparkWeeklyDistributionDocument to formatted JSON string."""
    return json.dumps(document.to_dict(), indent=indent)


def create_summary_bundle_gzip(
    documents: List[CarparkWeeklyDistributionDocument],
    generated_at: Optional[str] = None,
) -> bytes:
    """Serializes and compresses all carpark documents into a GZIP JSON bundle."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "metadata": {
            "version": DATAMART_SCHEMA_VERSION,
            "generated_at": generated_at,
        },
        "carparks": [doc.to_dict() for doc in documents],
    }
    raw_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw_json)
