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
        snapshot_count = 1
        data_count = 2

        lta_snapshots = lta_bronze_snapshot_generator(
            snapshot_count=snapshot_count,
            data_count=data_count,
        )
        hdb_snapshots = hdb_bronze_snapshot_generator(
            snapshot_count=snapshot_count,
            data_count=data_count,
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
        assert table.num_rows == snapshot_count * data_count

        # Test silver model
        rows = [
            SilverColdCarparkSnapshot.model_validate(row)
            for row in table.to_pylist()
        ]
        assert len(rows) == snapshot_count * data_count

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
    
    def test_transform_multiple_snapshots(
        self,
        lta_bronze_snapshot_generator,
        hdb_bronze_snapshot_generator,
    ):
        snapshot_count = 3
        data_count = 2

        lta_snapshots = lta_bronze_snapshot_generator(
            snapshot_count=snapshot_count,
            data_count=data_count,
        )

        hdb_snapshots = hdb_bronze_snapshot_generator(
            snapshot_count=snapshot_count,
            data_count=data_count,
        )

        ingestion_timestamp = "2026-08-11T09:00:13.432756+00:00"

        table = transform(
            lta_snapshots=lta_snapshots,
            hdb_snapshots=hdb_snapshots,
            ingestion_timestamp=ingestion_timestamp,
        )

        # Test schema
        assert table.schema == SILVER_PARQUET_SCHEMA

        # Test num rows
        assert table.num_rows == snapshot_count * data_count

        # Test silver model
        rows = [
            SilverColdCarparkSnapshot.model_validate(row)
            for row in table.to_pylist()
        ]

        assert len(rows) == snapshot_count * data_count

        for lta_snapshot, hdb_snapshot in zip(
            lta_snapshots,
            hdb_snapshots,
        ):
            snapshot_timestamp = datetime.fromisoformat(
                lta_snapshot["timestamp"]
            )

            # Find all Silver rows belonging to this snapshot
            snapshot_rows = [
                row
                for row in rows
                if row.snapshot_timestamp == snapshot_timestamp
            ]

            assert len(snapshot_rows) == data_count

            lta_values = lta_snapshot["value"]
            hdb_values = hdb_snapshot["value"]

            # Check every carpark in this snapshot
            for lta_value in lta_values:
                carpark_id = lta_value["CarParkID"]

                # Find corresponding HDB record
                hdb_value = next(
                    value
                    for value in hdb_values
                    if value["carpark_number"] == carpark_id
                )

                # Find corresponding Silver record
                silver_row = next(
                    row
                    for row in snapshot_rows
                    if row.carpark_id == carpark_id
                )

                # -------------------------
                # HDB → Silver
                # -------------------------

                hdb_info = hdb_value["carpark_info"][0]

                assert silver_row.lots_available == int(
                    hdb_info["lots_available"]
                )

                assert silver_row.total_lots == int(
                    hdb_info["total_lots"]
                )

                assert silver_row.lot_type == hdb_info["lot_type"]

                # -------------------------
                # LTA → Silver
                # -------------------------

                latitude, longitude = lta_value["Location"].split()

                assert silver_row.location_latitude == pytest.approx(
                    float(latitude)
                )

                assert silver_row.location_longitude == pytest.approx(
                    float(longitude)
                )

                assert silver_row.area == lta_value["Area"]
                assert silver_row.development == lta_value["Development"]
                assert silver_row.agency == lta_value["Agency"]

                # -------------------------
                # Shared fields
                # -------------------------

                assert silver_row.carpark_id == lta_value["CarParkID"]
                assert silver_row.carpark_id == hdb_value["carpark_number"]

                assert silver_row.snapshot_timestamp == snapshot_timestamp

        # Test ingestion timestamp
        expected_ingestion_timestamp = datetime.fromisoformat(
            ingestion_timestamp
        )

        assert all(
            row.ingestion_timestamp == expected_ingestion_timestamp
            for row in rows
        )


