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
    def test_transform_indiv_snapshot(self, lta_bronze_snapshot, hdb_bronze_snapshot):

        ingestion_timestamp = "2026-08-11T09:00:13.432756+00:00"

        table = transform(
            lta_snapshots=lta_bronze_snapshot,
            hdb_snapshots=hdb_bronze_snapshot,
            ingestion_timestamp=ingestion_timestamp,
        )

        assert table.schema == SILVER_PARQUET_SCHEMA

        table_list = table.to_pylist()

        # Validate every output row against the Pydantic model
        snapshots = [
            SilverColdCarparkSnapshot.model_validate(row)
            for row in table_list
        ]

        # Specific assertions
        snapshots.sort(key = lambda x: x.carpark_id)

        snapshot1 = snapshots[0]

        assert snapshot1.

