"""Data models defining the Carpark Availabilities JSON Datamart contract using standard library dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class PercentileStats:
    """Statistical five-number summary and key percentiles."""

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
        return asdict(self)


@dataclass(slots=True)
class Coordinates:
    """Geographical coordinates (WGS84)."""

    latitude: float
    longitude: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CarparkMetadata:
    """Metadata describing the carpark facility and vehicle lot type."""

    carpark_id: str
    lot_type: str
    lot_type_description: str
    agency: str
    has_capacity_data: bool
    development: Optional[str] = None
    area: Optional[str] = None
    total_lots: Optional[int] = None
    coordinates: Optional[Coordinates] = None

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
            "coordinates": self.coordinates.to_dict()
            if self.coordinates is not None
            else None,
        }


@dataclass(slots=True)
class HourlyDistribution:
    """Distribution metrics for a specific 1-hour time window on a given day of the week."""

    hour_of_day_sgt: int
    time_window: str
    observation_count: int
    lots_available: PercentileStats
    probability_full: float
    lots_occupied: Optional[PercentileStats] = None
    occupancy_rate: Optional[PercentileStats] = None
    probability_high_occupancy_ge_90pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour_of_day_sgt": self.hour_of_day_sgt,
            "time_window": self.time_window,
            "observation_count": self.observation_count,
            "lots_available": self.lots_available.to_dict(),
            "lots_occupied": self.lots_occupied.to_dict()
            if self.lots_occupied is not None
            else None,
            "occupancy_rate": self.occupancy_rate.to_dict()
            if self.occupancy_rate is not None
            else None,
            "probability_full": self.probability_full,
            "probability_high_occupancy_ge_90pct": self.probability_high_occupancy_ge_90pct,
        }


@dataclass(slots=True)
class DailySummary:
    """Aggregated daily statistical summary for an entire day of the week."""

    observation_count: int
    lots_available: PercentileStats
    probability_full: float
    lots_occupied: Optional[PercentileStats] = None
    occupancy_rate: Optional[PercentileStats] = None
    probability_high_occupancy_ge_90pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_count": self.observation_count,
            "lots_available": self.lots_available.to_dict(),
            "lots_occupied": self.lots_occupied.to_dict()
            if self.lots_occupied is not None
            else None,
            "occupancy_rate": self.occupancy_rate.to_dict()
            if self.occupancy_rate is not None
            else None,
            "probability_full": self.probability_full,
            "probability_high_occupancy_ge_90pct": self.probability_high_occupancy_ge_90pct,
        }


@dataclass(slots=True)
class DayDistribution:
    """Weekly pattern for a single day of the week (1=Monday ... 7=Sunday)."""

    day_name: str
    day_of_week: int
    is_weekend: bool
    daily_summary: Optional[DailySummary] = None
    hourly_distribution: List[HourlyDistribution] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_name": self.day_name,
            "day_of_week": self.day_of_week,
            "is_weekend": self.is_weekend,
            "daily_summary": self.daily_summary.to_dict()
            if self.daily_summary is not None
            else None,
            "hourly_distribution": [h.to_dict() for h in self.hourly_distribution],
        }


@dataclass(slots=True)
class DatamartMetadata:
    """Metadata regarding dataset generation, versioning, and time window."""

    generated_at: str
    version: str = "1.0.0"
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
    """Top-level document representing a carpark's weekly availability and occupancy patterns."""

    metadata: DatamartMetadata
    carpark: CarparkMetadata
    weekly_distribution: Dict[int, DayDistribution]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "carpark": self.carpark.to_dict(),
            "weekly_distribution": {
                k: v.to_dict() for k, v in self.weekly_distribution.items()
            },
        }
