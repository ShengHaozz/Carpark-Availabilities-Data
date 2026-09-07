"""Unit tests for the datamart JSON serialization contract."""

from datamart.schema import (
    CarparkMetadata,
    CarparkWeeklyDistributionDocument,
    Coordinates,
    DailySummary,
    DatamartMetadata,
    DayDistribution,
    HourlyDistribution,
    PercentileStats,
)


def percentile_stats() -> PercentileStats:
    return PercentileStats(
        min=1.0,
        p10=2.0,
        p25=3.0,
        p50=4.0,
        p75=5.0,
        p90=6.0,
        max=7.0,
        mean=4.5,
        std_dev=1.2,
    )


def carpark_metadata() -> CarparkMetadata:
    return CarparkMetadata(
        carpark_id="ACB",
        lot_type="C",
        lot_type_description="Car",
        development="Albert Centre",
        agency="HDB",
        area="Central",
        total_lots=500,
        has_capacity_data=True,
        coordinates=Coordinates(latitude=1.3012, longitude=103.8541),
    )


def test_percentile_stats_to_dict():
    stats = percentile_stats()

    assert stats.to_dict() == {
        "min": 1.0,
        "p10": 2.0,
        "p25": 3.0,
        "p50": 4.0,
        "p75": 5.0,
        "p90": 6.0,
        "max": 7.0,
        "mean": 4.5,
        "std_dev": 1.2,
    }


def test_coordinates_to_dict():
    coordinates = Coordinates(latitude=1.3012, longitude=103.8541)

    assert coordinates.to_dict() == {"latitude": 1.3012, "longitude": 103.8541}


def test_carpark_metadata_to_dict():
    carpark = carpark_metadata()

    assert carpark.to_dict() == {
        "carpark_id": "ACB",
        "lot_type": "C",
        "lot_type_description": "Car",
        "development": "Albert Centre",
        "agency": "HDB",
        "area": "Central",
        "total_lots": 500,
        "has_capacity_data": True,
        "coordinates": {"latitude": 1.3012, "longitude": 103.8541},
    }


def test_hourly_distribution_to_dict():
    stats = percentile_stats()
    hourly = HourlyDistribution(
        hour_of_day_sgt=8,
        time_window="08:00-08:59",
        observation_count=60,
        lots_available=stats,
        lots_occupied=None,
        occupancy_rate=stats,
        probability_full=0.1,
        probability_high_occupancy_ge_90pct=None,
    )

    assert hourly.to_dict() == {
        "hour_of_day_sgt": 8,
        "time_window": "08:00-08:59",
        "observation_count": 60,
        "lots_available": stats.to_dict(),
        "lots_occupied": None,
        "occupancy_rate": stats.to_dict(),
        "probability_full": 0.1,
        "probability_high_occupancy_ge_90pct": None,
    }


def test_daily_summary_to_dict():
    stats = percentile_stats()
    summary = DailySummary(
        observation_count=420,
        lots_available=stats,
        lots_occupied=stats,
        occupancy_rate=None,
        probability_full=0.2,
        probability_high_occupancy_ge_90pct=0.3,
    )

    assert summary.to_dict() == {
        "observation_count": 420,
        "lots_available": stats.to_dict(),
        "lots_occupied": stats.to_dict(),
        "occupancy_rate": None,
        "probability_full": 0.2,
        "probability_high_occupancy_ge_90pct": 0.3,
    }


def test_day_distribution_to_dict():
    stats = percentile_stats()
    summary = DailySummary(
        observation_count=420,
        lots_available=stats,
        lots_occupied=None,
        occupancy_rate=None,
        probability_full=0.2,
        probability_high_occupancy_ge_90pct=None,
    )
    hourly = HourlyDistribution(
        hour_of_day_sgt=8,
        time_window="08:00-08:59",
        observation_count=60,
        lots_available=stats,
        lots_occupied=None,
        occupancy_rate=None,
        probability_full=0.1,
        probability_high_occupancy_ge_90pct=None,
    )
    day = DayDistribution(
        day_name="Monday",
        day_of_week=1,
        is_weekend=False,
        daily_summary=summary,
        hourly_distribution=[hourly],
    )

    assert day.to_dict() == {
        "day_name": "Monday",
        "day_of_week": 1,
        "is_weekend": False,
        "daily_summary": summary.to_dict(),
        "hourly_distribution": [hourly.to_dict()],
    }


def test_datamart_metadata_to_dict():
    metadata = DatamartMetadata(
        version="v1",
        generated_at="2026-09-07T00:00:00+00:00",
        total_observations_analyzed=420,
    )

    assert metadata.to_dict() == {
        "version": "v1",
        "generated_at": "2026-09-07T00:00:00+00:00",
        "timezone": "Asia/Singapore (UTC+8)",
        "lookback_window_days": 60,
        "total_observations_analyzed": 420,
    }


def test_document_to_dict_assembles_component_serializers():
    stats = percentile_stats()
    metadata = DatamartMetadata(version="v1", generated_at="2026-09-07T00:00:00+00:00")
    carpark = carpark_metadata()
    hourly = HourlyDistribution(
        hour_of_day_sgt=8,
        time_window="08:00-08:59",
        observation_count=60,
        lots_available=stats,
        lots_occupied=None,
        occupancy_rate=None,
        probability_full=0.1,
        probability_high_occupancy_ge_90pct=None,
    )
    day = DayDistribution(
        day_name="Monday",
        day_of_week=1,
        is_weekend=False,
        daily_summary=None,
        hourly_distribution=[hourly],
    )
    document = CarparkWeeklyDistributionDocument(
        metadata=metadata,
        carpark=carpark,
        weekly_distribution={1: day},
    )

    assert document.to_dict() == {
        "metadata": metadata.to_dict(),
        "carpark": carpark.to_dict(),
        "weekly_distribution": {"1": day.to_dict()},
        "$schema": document.schema_url,
    }
