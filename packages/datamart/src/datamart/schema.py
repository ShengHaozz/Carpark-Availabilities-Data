"""Python standard library dataclass models defining the Carpark Availabilities JSON Datamart contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


@dataclass(slots=True)
class Coordinates:
    """Geographical coordinates (WGS84)."""

    latitude: float
    longitude: float


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


@dataclass(slots=True)
class DailySummary:
    """Aggregated daily statistical summary for an entire day of the week."""

    observation_count: int
    lots_available: PercentileStats
    lots_occupied: Optional[PercentileStats]
    occupancy_rate: Optional[PercentileStats]
    probability_full: float
    probability_high_occupancy_ge_90pct: Optional[float]


@dataclass(slots=True)
class DayDistribution:
    """Weekly pattern for a single day of the week (1=Monday ... 7=Sunday)."""

    day_name: str
    day_of_week: int
    is_weekend: bool
    daily_summary: Optional[DailySummary]
    hourly_distribution: List[HourlyDistribution] = field(default_factory=list)


@dataclass(slots=True)
class DatamartMetadata:
    """Metadata regarding dataset generation, versioning, and time window."""

    version: str = DATAMART_SCHEMA_VERSION
    generated_at: str = ""
    timezone: str = "Asia/Singapore (UTC+8)"
    lookback_window_days: int = 60
    total_observations_analyzed: Optional[int] = None


@dataclass(slots=True)
class CarparkWeeklyDistributionDocument:
    """Top-level JSON document representing a carpark's weekly availability and occupancy patterns."""

    metadata: DatamartMetadata
    carpark: CarparkMetadata
    weekly_distribution: Dict[int, DayDistribution]
    schema_url: str = "https://json-schema.org/draft/2020-12/schema"

    def to_dict(self) -> Dict[str, Any]:
        """Custom dictionary serializer converting integer day keys to strings for JSON compatibility."""
        data = asdict(self)
        # Rename schema_url to $schema for JSON Schema standard
        data["$schema"] = data.pop("schema_url")
        if "weekly_distribution" in data and isinstance(
            data["weekly_distribution"], dict
        ):
            data["weekly_distribution"] = {
                str(k): v for k, v in data["weekly_distribution"].items()
            }
        return data
