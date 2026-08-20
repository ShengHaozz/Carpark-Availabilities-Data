import pytest
import pyarrow as pa
from datetime import datetime
from packages.silver_cold.src.silver_cold import (
    get_snapshots_from_bucket,
    transform,
    upload_silver_table_parts_to_s3,
    handler,
    SilverColdCarparkSnapshot,
    SILVER_PARQUET_SCHEMA
)

class Test_Silver_Cold:
    def test_transform_indiv_snapshot(self, lta_bronze_snapshot_generator, hdb_bronze_snapshot_generator):

        lta_snapshots = lta_bronze_snapshot_generator(
            snapshot_count=1,
            data_count=2,
        )
        hdb_snapshots = hdb_bronze_snapshot_generator(
            snapshot_count=1,
            data_count=2,
        )

        ingestion_timestamp = "2026-08-11T09:00:13.432756+00:00"

        table = transform(
            lta_snapshots=lta_snapshots,
            hdb_snapshots=hdb_snapshots,
            ingestion_timestamp=ingestion_timestamp,
        )

        # Schema
        assert table.schema == SILVER_PARQUET_SCHEMA

