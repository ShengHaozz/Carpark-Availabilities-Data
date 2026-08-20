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
        SNAPSHOT_COUNT = 1
        DATA_COUNT = 2

        lta_snapshots = lta_bronze_snapshot_generator()(
            snapshot_count=SNAPSHOT_COUNT,
            data_count=DATA_COUNT,
        )
        hdb_snapshots = hdb_bronze_snapshot_generator()(
            snapshot_count=SNAPSHOT_COUNT,
            data_count=DATA_COUNT,
        )

        ingestion_timestamp = "2026-08-11T09:00:13.432756+00:00"

        table = transform(
            lta_snapshots=lta_snapshots,
            hdb_snapshots=hdb_snapshots,
            ingestion_timestamp=ingestion_timestamp,
        )

        # Test Schema
        assert table.schema == SILVER_PARQUET_SCHEMA

        # Test 1 snapshot x 2 rows
        assert table.num_rows == SNAPSHOT_COUNT * DATA_COUNT

        # Test silver model
        rows = [
            SilverColdCarparkSnapshot.model_validate(row)
            for row in table.to_pylist()
        ]
        assert len(rows) == SNAPSHOT_COUNT * DATA_COUNT

        # Reference original Bronze data
        lta_values = lta_snapshots[0]["value"]
        hdb_values = hdb_snapshots[0]["value"]

        for row in rows:
            carpark_id = row.carpark_id

            lta_value = next(
                (value
                for value in lta_values
                if value["CarParkID"] == carpark_id),
                default = None
            )

            hdb_value = next(
                (value
                for value in hdb_values
                if value["carpark_number"] == carpark_id),
                default = None
            )

            # Test matching lta and hdb value
            assert lta_value
            assert hdb_value

            # Test HDB Data
            assert row.lots_available == int(
                hdb_value["carpark_info"][0]["lots_available"]
            )

            assert row.total_lots == int(
                hdb_value["carpark_info"][0]["total_lots"]
            )

            assert row.lot_type == hdb_value["carpark_info"][0]["lot_type"]

            # Test LTA values
            latitude, longitude = lta_value["Location"].split()

            assert row.location_latitude == pytest.approx(
                float(latitude)
            )

            assert row.location_longitude == pytest.approx(
                float(longitude)
            )

            assert row.area == lta_value["Area"]
            assert row.development == lta_value["Development"]
            assert row.agency == lta_value["Agency"]

            # Test snapshot timestamp comes from the LTA Bronze snapshot
            assert row.snapshot_timestamp == datetime.fromisoformat(
                lta_snapshots[0]["timestamp"]
            )

            # Test ingestion timestamp comes from the transform argument
            assert row.ingestion_timestamp == datetime.fromisoformat(
                ingestion_timestamp
            )


