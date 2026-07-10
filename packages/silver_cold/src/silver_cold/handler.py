import boto3
from models import SILVER_PARQUET_SCHEMA, BronzeSnapshot, DatamallCarparkAvailability, HDBCarparkData, SilverColdCarparkSnapshot
import os
import json
from typing import Callable
from datetime import datetime
from pydantic import TypeAdapter
import pyarrow as pa

BUCKET = os.environ["BUCKET_NAME"]
INPUT_LEVEL = os.environ["INPUT_LEVEL"]
LTA_SOURCE = os.environ["LTA_SOURCE"]
HDB_SOURCE = os.environ["HDB_SOURCE"]
OUTPUT_LEVEL = os.environ["OUTPUT_LEVEL"]

KEY_PREFIX = (
    "level={level}/"
    "source={source}/"
    "year={year:02d}/"
    "month={month:02d}/"
    "day={day:02d}/"
)

ingestion_timestamp = datetime.now()

def get_snapshots_from_bucket[T](
        paginator,
        prefix: str, 
        validator: Callable[[dict], T],
        bucket: str = BUCKET
    ) -> list[T]:

    snapshots: list[T] = []

    for page in paginator.paginate(Bucket = bucket, Prefix = prefix): # Each folder
        for obj in page.get("Content", []): # Each file in the folder
            filepath_str = obj["Key"] 

            if filepath_str.endswith('/'): # placeholder directories
                continue
            
            response = s3.get_object(
                Bucket = bucket,
                Key = filepath_str
            )

            with response['Body'] as body:
                data = json.loads(body.read())
            
            snapshot = validator(data)
            snapshots.append(snapshot)

    return snapshots

def transform(
        lta_snapshots: list[BronzeSnapshot[DatamallCarparkAvailability]],
        hdb_snapshots: list[BronzeSnapshot[HDBCarparkData]],
        ingestion_timestamp: datetime
    ) -> pa.Table:

    lta_snapshots.sort(key = lambda x: x.timestamp)
    hdb_info_d = {(snapshot.timestamp, hdb_data.carpark_number): hdb_data.carpark_info for snapshot in hdb_snapshots for hdb_data in snapshot.values}
    
    silver_data: list[dict] = []

    for lta_snapshot in lta_snapshots:
        lta_data = lta_snapshot.values
        timestamp = lta_snapshot.timestamp

        for lta_datapoint in lta_data:
            
            
            silver_datapoint = {
                'carpark_id': lta_datapoint.CarParkID,
                'snapshot_timestamp': timestamp,
                'lot_type': lta_datapoint.LotType,
                'lots_available': lta_datapoint.AvailableLots,
                'location_latitude': lta_datapoint.LocationLatLong[0],
                'location_longitude': lta_datapoint.LocationLatLong[1],
                'area': lta_datapoint.Area,
                'development': lta_datapoint.Development,
                'agency': lta_datapoint.Agency,
                'ingestion_timestamp': ingestion_timestamp,
            }
            
            # SilverColdCarparkSnapshot(
            #     carpark_id = lta_datapoint.CarParkID,
            #     snapshot_timestamp = timestamp,
            #     lot_type = lta_datapoint.LotType,
            #     lots_available = lta_datapoint.AvailableLots,
            #     location_latitude = lta_datapoint.LocationLatLong[0],
            #     location_longitude = lta_datapoint.LocationLatLong[1],
            #     area = lta_datapoint.Area,
            #     development = lta_datapoint.Development,
            #     Agency = lta_datapoint.Agency,
            #     ingestion_timestamp = ingestion_timestamp,
            #     source_filepath = lta_snapshot.source_filepath
            # )

            if (timestamp, lta_datapoint.CarParkID) in hdb_info_d:
                hdb_info = hdb_info_d[(timestamp, lta_datapoint.CarParkID)]
                silver_datapoint['lots_available'] = hdb_info.lots_available
                silver_datapoint['lot_type'] = hdb_info.lot_type
                silver_datapoint['total_lots'] = hdb_info.total_lots

            silver_data.append(silver_datapoint)

    silver_table = pa.Table.from_pylist(silver_data, schema = SILVER_PARQUET_SCHEMA)
    return silver_table

"""
event = {
    year: int,
    month: int,
    day: int
}
"""

def handler(event, context):
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')

    lta_key_prefix = KEY_PREFIX.format(
        level = INPUT_LEVEL,
        source = LTA_SOURCE,
        year = event["year"],
        month = event["month"],
        day = event["day"]
    )

    lta_adapter = TypeAdapter(BronzeSnapshot[DatamallCarparkAvailability])

    hdb_key_prefix = KEY_PREFIX.format(
        level = INPUT_LEVEL,
        source = HDB_SOURCE,
        year = event["year"],
        month = event["month"],
        day = event["day"]
    )

    hdb_adapter = TypeAdapter(BronzeSnapshot[HDBCarparkData])

    lta_snapshots = get_snapshots_from_bucket(
        paginator = paginator,
        prefix = lta_key_prefix,
        validator = lta_adapter.validate_python
    )

    hdb_snapshots = get_snapshots_from_bucket(
        paginator = paginator,
        prefix = hdb_key_prefix,
        validator = hdb_adapter.validate_python
    )

    silver_table = transform(
        lta_snapshots = lta_snapshots,
        hdb_snapshots = hdb_snapshots,
        ingestion_timestamp = ingestion_timestamp
    )