"""Python standard library dataclass models defining the Carpark Availabilities JSON Datamart contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DATAMART_SCHEMA_VERSION: str = "1.0.0"
DATAMART_API_VERSION: str = "v1"


@dataclass(slots=True)
class PercentileStats:
    """Statistical summary and key percentiles."""

    min: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    max: float
    mean: float
    std_dev: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min": self.min,
            "p10": self.p10,
            "p25": self.p25,
            "p50": self.p50,
            "p75": self.p75,
            "p90": self.p90,
            "max": self.max,
            "mean": self.mean,
            "std_dev": self.std_dev,
        }


@dataclass(slots=True)
class Coordinates:
    """Geographical coordinates (WGS84)."""

    latitude: float
    longitude: float

    def to_dict(self) -> Dict[str, Any]:
        return {"latitude": self.latitude, "longitude": self.longitude}


@dataclass(slots=True)
class CarparkMetadata:
    """Metadata describing the carpark facility and vehicle lot type."""

    carpark_id: str
    lot_type: str
    lot_type_description: str
    development: Optional[str]
    agency: str
    area: Optional[str]
    total_lots: Optional[int]
    has_capacity_data: bool
    coordinates: Optional[Coordinates]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "carpark_id": self.carpark_id,
            "lot_type": self.lot_type,
            "lot_type_description": self.lot_type_description,
            "development": self.development,
            "agency": self.agency,
            "area": self.area,
            "total_lots": self.total_lots,
            "has_capacity_data": self.has_capacity_data,
            "coordinates": (
                self.coordinates.to_dict() if self.coordinates is not None else None
            ),
        }


@dataclass(slots=True)
class HourlyDistribution:
    """Distribution metrics for a specific 1-hour time window on a given day of the week."""

    hour_of_day_sgt: int
    time_window: str
    observation_count: int
    lots_available: PercentileStats
    lots_occupied: Optional[PercentileStats]
    occupancy_rate: Optional[PercentileStats]
    probability_full: float
    probability_high_occupancy_ge_90pct: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour_of_day_sgt": self.hour_of_day_sgt,
            "time_window": self.time_window,
            "observation_count": self.observation_count,
            "lots_available": self.lots_available.to_dict(),
            "lots_occupied": (
                self.lots_occupied.to_dict() if self.lots_occupied is not None else None
            ),
            "occupancy_rate": (
                self.occupancy_rate.to_dict()
                if self.occupancy_rate is not None
                else None
            ),
            "probability_full": self.probability_full,
            "probability_high_occupancy_ge_90pct": self.probability_high_occupancy_ge_90pct,
        }


@dataclass(slots=True)
class DailySummary:
    """Aggregated daily statistical summary for an entire day of the week."""

    observation_count: int
    lots_available: PercentileStats
    lots_occupied: Optional[PercentileStats]
    occupancy_rate: Optional[PercentileStats]
    probability_full: float
    probability_high_occupancy_ge_90pct: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_count": self.observation_count,
            "lots_available": self.lots_available.to_dict(),
            "lots_occupied": (
                self.lots_occupied.to_dict() if self.lots_occupied is not None else None
            ),
            "occupancy_rate": (
                self.occupancy_rate.to_dict()
                if self.occupancy_rate is not None
                else None
            ),
            "probability_full": self.probability_full,
            "probability_high_occupancy_ge_90pct": self.probability_high_occupancy_ge_90pct,
        }


@dataclass(slots=True)
class DayDistribution:
    """Weekly pattern for a single day of the week (1=Monday ... 7=Sunday)."""

    day_name: str
    day_of_week: int
    is_weekend: bool
    daily_summary: Optional[DailySummary]
    hourly_distribution: List[HourlyDistribution] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_name": self.day_name,
            "day_of_week": self.day_of_week,
            "is_weekend": self.is_weekend,
            "daily_summary": (
                self.daily_summary.to_dict() if self.daily_summary is not None else None
            ),
            "hourly_distribution": [
                hour.to_dict() for hour in self.hourly_distribution
            ],
        }


@dataclass(slots=True)
class DatamartMetadata:
    """Metadata regarding dataset generation, versioning, and time window."""

    version: str = DATAMART_SCHEMA_VERSION
    generated_at: str = ""
    timezone: str = "Asia/Singapore (UTC+8)"
    lookback_window_days: int = 60
    total_observations_analyzed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "timezone": self.timezone,
            "lookback_window_days": self.lookback_window_days,
            "total_observations_analyzed": self.total_observations_analyzed,
        }


@dataclass(slots=True)
class CarparkWeeklyDistributionDocument:
    """Top-level JSON document representing a carpark's weekly availability and occupancy patterns."""

    metadata: DatamartMetadata
    carpark: CarparkMetadata
    weekly_distribution: Dict[int, DayDistribution]
    schema_url: str = "https://json-schema.org/draft/2020-12/schema"

    def to_dict(self) -> Dict[str, Any]:
        """Custom dictionary serializer converting integer day keys to strings for JSON compatibility."""
        return {
            "metadata": self.metadata.to_dict(),
            "carpark": self.carpark.to_dict(),
            "weekly_distribution": {
                str(day): distribution.to_dict()
                for day, distribution in self.weekly_distribution.items()
            },
            "$schema": self.schema_url,
        }
