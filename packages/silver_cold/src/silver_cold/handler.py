from collections.abc import Iterable, Iterator

import boto3
from .models import (
    SILVER_PARQUET_SCHEMA,
    BronzeSnapshot,
    DatamallCarparkAvailability,
    HDBCarparkData,
)
import os
import json
from typing import Callable, Any
from datetime import datetime, timezone, timedelta
from pydantic import TypeAdapter, ValidationError
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

HOURS_IN_DAY = 24

KEY_PREFIX = (
    "level={level}/"
    "source={source}/"
    "year={year:02d}/"
    "month={month:02d}/"
    "day={day:02d}/"
    "hour={{hour:02d}}"
)

ingestion_timestamp = datetime.now(tz=timezone.utc)


def get_snapshots_from_bucket[T](
    s3_client: Any, prefix: str, validator: Callable[[dict], T], bucket: str
) -> list[T]:

    snapshots: list[T] = []

    for page in s3_client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):  # Each folder
        for obj in page.get("Contents", []):  # Each file in the folder
            filepath_str = obj["Key"]

            if filepath_str.endswith("/"):  # placeholder directories
                continue

            response = s3_client.get_object(Bucket=bucket, Key=filepath_str)

            with response["Body"] as body:
                data = json.loads(body.read())
            try:
                data["source_filepath"] = filepath_str
                snapshot = validator(data)
            except ValidationError as e:
                print("DATA:")
                print("=" * 10)
                print(data)
                raise e

            snapshots.append(snapshot)

    return snapshots


def transform(
    lta_snapshots: list[BronzeSnapshot[DatamallCarparkAvailability]],
    hdb_snapshots: list[BronzeSnapshot[HDBCarparkData]],
    ingestion_timestamp: datetime,
) -> pa.Table:

    lta_snapshots.sort(key=lambda x: x.timestamp)
    hdb_info_d = {
        (snapshot.timestamp, hdb_data.carpark_number): hdb_data.carpark_info[0]
        for snapshot in hdb_snapshots
        for hdb_data in snapshot.value
    }

    silver_data: list[dict] = []

    for lta_snapshot in lta_snapshots:
        lta_data = lta_snapshot.value
        timestamp = lta_snapshot.timestamp

        for lta_datapoint in lta_data:
            silver_datapoint = {
                "carpark_id": lta_datapoint.CarParkID,
                "snapshot_timestamp": timestamp,
                "lot_type": lta_datapoint.LotType,
                "lots_available": lta_datapoint.AvailableLots,
                "location_latitude": lta_datapoint.LocationLatLong[0],
                "location_longitude": lta_datapoint.LocationLatLong[1],
                "area": lta_datapoint.Area,
                "development": lta_datapoint.Development,
                "agency": lta_datapoint.Agency,
                "ingestion_timestamp": ingestion_timestamp,
                "source_filepath": lta_snapshot.source_filepath,
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
                silver_datapoint["lots_available"] = hdb_info.lots_available
                silver_datapoint["lot_type"] = hdb_info.lot_type
                silver_datapoint["total_lots"] = hdb_info.total_lots

            silver_data.append(silver_datapoint)

    silver_table = pa.Table.from_pylist(silver_data, schema=SILVER_PARQUET_SCHEMA)
    return silver_table


def upload_silver_table_parts_to_s3(
    silver_table_parts: Iterable[pa.Table],
    reference_timestamp: datetime,
    bucket: str,
    level: str,
) -> None:

    key = (
        f"level={level}/"
        f"year={reference_timestamp.year}/"
        f"month={reference_timestamp.month:02d}/"
        f"day={reference_timestamp.day:02d}/"
        f"silver_cold.parquet"
    )

    s3fs = pafs.S3FileSystem()
    with s3fs.open_output_stream(f"{bucket}/{key}") as stream:
        writer = pq.ParquetWriter(
            stream,
            SILVER_PARQUET_SCHEMA,
            compression="zstd",
        )

        try:
            for table_part in silver_table_parts:
                writer.write_table(table_part)

        finally:
            writer.close()


"""
event = {
    year: int,
    month: int,
    day: int
}
"""


def handler(event, context):
    BUCKET = os.environ["BUCKET_NAME"]
    INPUT_LEVEL = os.environ["INPUT_LEVEL"]
    LTA_SOURCE = os.environ["LTA_SOURCE"]
    HDB_SOURCE = os.environ["HDB_SOURCE"]
    OUTPUT_LEVEL = os.environ["OUTPUT_LEVEL"]

    s3 = boto3.client("s3")

    dt = datetime.fromisoformat(event["time"].replace("Z", "+00:00")) - timedelta(
        days=1
    )

    lta_key_prefix = KEY_PREFIX.format(
        level=INPUT_LEVEL, source=LTA_SOURCE, year=dt.year, month=dt.month, day=dt.day
    )

    lta_adapter = TypeAdapter(BronzeSnapshot[DatamallCarparkAvailability])

    hdb_key_prefix = KEY_PREFIX.format(
        level=INPUT_LEVEL, source=HDB_SOURCE, year=dt.year, month=dt.month, day=dt.day
    )

    hdb_adapter = TypeAdapter(BronzeSnapshot[HDBCarparkData])

    def table_part_generator() -> Iterator[pa.Table]:
        for hour in range(HOURS_IN_DAY):
            print(f"Fetching /hour={hour:02d}")
            lta_snapshots = get_snapshots_from_bucket(
                s3_client=s3,
                prefix=lta_key_prefix.format(hour=hour),
                validator=lta_adapter.validate_python,
                bucket=BUCKET,
            )
            print(f"Fetched {len(lta_snapshots)} LTA snapshots")

            hdb_snapshots = get_snapshots_from_bucket(
                s3_client=s3,
                prefix=hdb_key_prefix.format(hour=hour),
                validator=hdb_adapter.validate_python,
                bucket=BUCKET,
            )
            print(f"Fetched {len(hdb_snapshots)} HDB snapshots")

            print("Transforming snapshots into silver table")
            silver_table_part = transform(
                lta_snapshots=lta_snapshots,
                hdb_snapshots=hdb_snapshots,
                ingestion_timestamp=ingestion_timestamp,
            )
            print(f"Created table of {silver_table_part.num_rows} rows")

            yield silver_table_part

    print("Uploading silver table to S3")
    upload_silver_table_parts_to_s3(
        silver_table_parts=table_part_generator(),
        reference_timestamp=dt,
        bucket=BUCKET,
        level=OUTPUT_LEVEL,
    )

    return {
        "status": "SUCCESS",
        "processed_date": dt.strftime("%Y-%m-%d"),
        "level": OUTPUT_LEVEL,
    }
