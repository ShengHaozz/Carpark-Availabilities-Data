import traceback

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
import pyarrow as pa

# TODO: Change value -> values in bronze and silver

class BronzeSnapshot[T](BaseModel):
    timestamp: datetime
    source: str
    poll_start: datetime
    poll_end: datetime
    pages: int
    records_count: int
    value: list[T]

class DatamallCarparkAvailability(BaseModel):
    CarParkID: str
    Area: str | None = None
    Development: str | None = None
    Location: str
    AvailableLots: int = Field(ge = 0)
    LotType: Literal['C', 'H', 'Y']
    Agency: Literal['HDB', 'LTA', 'URA']

    @property
    def LocationLatLong(self) -> tuple[float | None, float | None]:
        return self._parse_location()

    def _parse_location(self) -> tuple[float | None, float | None]:
        try:
            parts = self.Location.split()
            if len(parts) != 2:
                print(f"Could not parse Location {self.Location} for CarparkID {self.CarParkID}")
                return None, None
            return float(parts[0]), float(parts[1])
        except Exception as e:
            print(f"Could not parse Location {self.Location} for CarparkID {self.CarParkID}")
            print(f"Exception: {e}")
            traceback.print_exc()
            return None, None

class HDBCarparkInfo(BaseModel):
    lots_available: int = Field(ge = 0)
    lot_type: Literal['C', 'H', 'S', 'Y', 'unknown'] = 'unknown'
    total_lots: int = Field(ge = 0)

class HDBCarparkData(BaseModel) :
    carpark_info: HDBCarparkInfo
    carpark_number: str
    update_datetime: str


class SilverColdCarparkSnapshot(BaseModel):
    carpark_id: str
    snapshot_timestamp: datetime
    lot_type: Literal['C', 'H', 'S', 'Y', 'unknown']
    lots_available: int = Field(ge = 0)
    total_lots: int | None = Field(default = None, ge = 0)
    location_latitude: float | None = None
    location_longitude: float | None = None
    area: str | None = None
    development: str | None = None
    agency: Literal['HDB', 'LTA', 'URA']
    ingestion_timestamp: datetime
    source_filepath: str

SILVER_PARQUET_SCHEMA = pa.schema([
    pa.field("carpark_id", pa.string(), nullable=False),
    pa.field("snapshot_timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("lot_type", pa.string(), nullable=False),
    pa.field("lots_available", pa.int32(), nullable=False),
    pa.field("total_lots", pa.int32(), nullable=True),
    pa.field("location_latitude", pa.float64(), nullable=True),
    pa.field("location_longitude", pa.float64(), nullable=True),
    pa.field("area", pa.string(), nullable=True),
    pa.field("development", pa.string(), nullable=True),
    pa.field("agency", pa.string(), nullable=False),
    pa.field("ingestion_timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("source_filepath", pa.string(), nullable=False),
])