"""Pydantic data models defining the Carpark Availabilities JSON Datamart contract."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PercentileStats(BaseModel):
    """Statistical five-number summary and key percentiles."""

    model_config = ConfigDict(extra="forbid")

    min: float = Field(..., description="Minimum observed value.")
    p10: float = Field(..., description="10th percentile observation.")
    p25: float = Field(..., description="25th percentile (1st quartile) observation.")
    p50: float = Field(..., description="50th percentile (median) observation.")
    p75: float = Field(..., description="75th percentile (3rd quartile) observation.")
    p90: float = Field(..., description="90th percentile observation.")
    max: float = Field(..., description="Maximum observed value.")
    mean: float = Field(..., description="Arithmetic mean.")
    std_dev: float = Field(..., description="Sample standard deviation.")


class Coordinates(BaseModel):
    """Geographical coordinates (WGS84)."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., description="Latitude coordinate in Singapore.")
    longitude: float = Field(..., description="Longitude coordinate in Singapore.")


class CarparkMetadata(BaseModel):
    """Metadata describing the carpark facility and vehicle lot type."""

    model_config = ConfigDict(extra="forbid")

    carpark_id: str = Field(..., description="Unique carpark identifier.")
    lot_type: str = Field(..., description="Vehicle lot type code (e.g., C, H, Y).")
    lot_type_description: str = Field(
        ..., description="Human-readable lot type (e.g. Cars, Motorcycles)."
    )
    development: Optional[str] = Field(
        None, description="Development or location name."
    )
    agency: str = Field(..., description="Managing agency (HDB, LTA, URA).")
    area: Optional[str] = Field(None, description="Regional area or district.")
    total_lots: Optional[int] = Field(
        None, description="Total parking capacity (null if unknown/non-HDB)."
    )
    has_capacity_data: bool = Field(
        ...,
        description="True if total_lots and occupancy stats are available; false otherwise.",
    )
    coordinates: Optional[Coordinates] = Field(
        None, description="Physical coordinates if known."
    )


class HourlyDistribution(BaseModel):
    """Distribution metrics for a specific 1-hour time window on a given day of the week."""

    model_config = ConfigDict(extra="forbid")

    hour_of_day_sgt: int = Field(
        ..., ge=0, le=23, description="Hour of day in Singapore Time (0 to 23)."
    )
    time_window: str = Field(
        ..., description="Human-readable hour window (e.g., '08:00 - 08:59')."
    )
    observation_count: int = Field(
        ..., ge=0, description="Number of snapshot observations analyzed."
    )
    lots_available: PercentileStats = Field(
        ..., description="Distribution of available parking spaces."
    )
    lots_occupied: Optional[PercentileStats] = Field(
        None, description="Distribution of occupied lots (null if capacity unknown)."
    )
    occupancy_rate: Optional[PercentileStats] = Field(
        None, description="Distribution of occupancy percentage (0.0 to 1.0)."
    )
    probability_full: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Empirical probability of 0 available spaces.",
    )
    probability_high_occupancy_ge_90pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Empirical probability of occupancy >= 90% (null if capacity unknown).",
    )


class DailySummary(BaseModel):
    """Aggregated daily statistical summary for an entire day of the week."""

    model_config = ConfigDict(extra="forbid")

    observation_count: int = Field(
        ..., ge=0, description="Total daily observations across all 24 hours."
    )
    lots_available: PercentileStats = Field(
        ..., description="Full-day distribution of available parking spaces."
    )
    lots_occupied: Optional[PercentileStats] = Field(
        None,
        description="Full-day distribution of occupied lots (null if capacity unknown).",
    )
    occupancy_rate: Optional[PercentileStats] = Field(
        None,
        description="Full-day distribution of occupancy rate (null if capacity unknown).",
    )
    probability_full: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Full-day probability of 0 available spaces.",
    )
    probability_high_occupancy_ge_90pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Full-day probability of occupancy >= 90% (null if capacity unknown).",
    )


class DayDistribution(BaseModel):
    """Weekly pattern for a single day of the week (1=Monday ... 7=Sunday)."""

    model_config = ConfigDict(extra="forbid")

    day_name: str = Field(
        ..., description="Day name (e.g., 'Monday', 'Tuesday', ..., 'Sunday')."
    )
    day_of_week: int = Field(
        ..., ge=1, le=7, description="ISO day of week (1=Monday ... 7=Sunday)."
    )
    is_weekend: bool = Field(..., description="True for Saturday and Sunday.")
    daily_summary: Optional[DailySummary] = Field(
        None, description="Aggregated full-day summary."
    )
    hourly_distribution: List[HourlyDistribution] = Field(
        default_factory=list, description="Hourly distribution slots (0 to 23)."
    )


class DatamartMetadata(BaseModel):
    """Metadata regarding dataset generation, versioning, and time window."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="1.0.0", description="Schema version.")
    generated_at: str = Field(
        ..., description="ISO 8601 timestamp with timezone when generated."
    )
    timezone: str = Field(
        default="Asia/Singapore (UTC+8)",
        description="Timezone used for day/hour binning.",
    )
    lookback_window_days: int = Field(
        default=60, description="Number of historical days aggregated."
    )
    total_observations_analyzed: Optional[int] = Field(
        None, description="Total observation count across all days."
    )


class CarparkWeeklyDistributionDocument(BaseModel):
    """Top-level JSON document representing a carpark's weekly availability and occupancy patterns."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    schema_url: Optional[str] = Field(
        default="https://json-schema.org/draft/2020-12/schema",
        alias="$schema",
        description="JSON Schema URI.",
    )
    metadata: DatamartMetadata
    carpark: CarparkMetadata
    weekly_distribution: Dict[str, DayDistribution] = Field(
        ...,
        description="Distribution keyed by day of week ('1' for Monday to '7' for Sunday).",
    )
