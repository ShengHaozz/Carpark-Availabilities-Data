from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class DatamallCarparkAvailability(BaseModel):
    CarParkID: str
    Area: str | None = None
    Development: str | None = None
    Location: str
    AvailableLots: int = Field(ge = 0)
    LotType: Literal['C', 'H', 'Y']
    Agency: Literal['HDB', 'LTA', 'URA']

class HDBCarparkInfo(BaseModel):
    lots_available: int = Field(ge = 0)
    lot_type: str = Literal['C', 'H', 'S', 'Y']
    total_lots: int = Field(ge = 0)

class HDBCarparkData(BaseModel) :
    carpark_info: HDBCarparkInfo
    carpark_number: str
    update_datetime: str


class SilverColdCarparkSnapshot(BaseModel):
    carpark_id: str
    snapshot_timestamp: datetime
    lot_type: str = Literal['C', 'H', 'Y', 'unknown']
    lots_available: int = Field(ge = 0)
    total_lots: int | None = Field(default = None, ge = 0)
    location_latitude: float | None = None
    location_longitude: float | None = None
    area: str | None = None
    development: str | None = None
    Agency: Literal['HDB', 'LTA', 'URA']
    ingestion_timestamp: datetime
    source_filepath: str

