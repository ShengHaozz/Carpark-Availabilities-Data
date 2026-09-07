"""Unit tests for datamart.publisher and datamart.handler modules."""

import io
from unittest.mock import MagicMock, patch

import pytest

from datamart.handler import handler
from datamart.publisher import (
    publish_datamart_to_s3,
    read_mart_csv_from_s3,
)


def test_read_mart_csv_from_s3_with_header():
    """Verifies reading and type casting of delimited results with a header row."""
    delimiter = "\x01"
    csv_content = (
        "\n".join(
            (
                delimiter.join(
                    [
                        "carpark_id",
                        "lot_type",
                        "day_of_week",
                        "hour_of_day_sgt",
                        "observation_count",
                        "lots_avail_min",
                        "lots_avail_median",
                        "occupancy_median",
                        "is_weekend",
                        "has_capacity_data",
                        "agency",
                    ]
                ),
                delimiter.join(
                    [
                        "ACB",
                        "C",
                        "1",
                        "8",
                        "60",
                        "10.0",
                        "80.0",
                        "0.8400",
                        "false",
                        "true",
                        "HDB",
                    ]
                ),
                delimiter.join(
                    [
                        "SUNTEC",
                        "C",
                        "1",
                        "12",
                        "60",
                        "50.0",
                        "450.0",
                        "",
                        "false",
                        "false",
                        "LTA",
                    ]
                ),
            )
        )
        + "\n"
    )

    mock_s3 = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "level=mart/target=publisher/data.csv",
                    "Size": len(csv_content),
                }
            ]
        }
    ]
    mock_s3.get_paginator.return_value = mock_paginator
    mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_content.encode("utf-8"))}

    rows = read_mart_csv_from_s3(
        s3_bucket="test-bucket",
        prefix="level=mart/target=publisher",
        s3_client=mock_s3,
    )

    assert len(rows) == 2

    # HDB row assertions
    hdb_row = rows[0]
    assert hdb_row["carpark_id"] == "ACB"
    assert hdb_row["day_of_week"] == 1
    assert hdb_row["hour_of_day_sgt"] == 8
    assert hdb_row["lots_avail_min"] == 10.0
    assert hdb_row["lots_avail_median"] == 80.0
    assert hdb_row["occupancy_median"] == 0.8400
    assert hdb_row["is_weekend"] is False
    assert hdb_row["has_capacity_data"] is True

    # Non-HDB row assertions
    non_hdb_row = rows[1]
    assert non_hdb_row["carpark_id"] == "SUNTEC"
    assert non_hdb_row["occupancy_median"] is None
    assert non_hdb_row["has_capacity_data"] is False


def test_read_mart_csv_from_s3_without_header():
    """Verifies delimiter-safe raw mart rows preserve commas in metadata."""
    # 45 columns matching MART_COLUMNS
    raw_row = [
        "dist-123",  # distribution_id
        "ACB",  # carpark_id
        "C",  # lot_type
        "1",  # day_of_week
        "Monday",  # day_name
        "false",  # is_weekend
        "8",  # hour_of_day_sgt
        "60",  # observation_count
        "10.0",  # lots_avail_min
        "20.0",  # lots_avail_p10
        "40.0",  # lots_avail_p25
        "80.0",  # lots_avail_median
        "120.0",  # lots_avail_p75
        "160.0",  # lots_avail_p90
        "200.0",  # lots_avail_max
        "85.5",  # lots_avail_mean
        "32.1",  # lots_avail_stddev
        "300.0",  # lots_occ_min
        "340.0",  # lots_occ_p10
        "380.0",  # lots_occ_p25
        "420.0",  # lots_occ_median
        "460.0",  # lots_occ_p75
        "480.0",  # lots_occ_p90
        "490.0",  # lots_occ_max
        "414.5",  # lots_occ_mean
        "32.1",  # lots_occ_stddev
        "0.6000",  # occupancy_min
        "0.6800",  # occupancy_p10
        "0.7600",  # occupancy_p25
        "0.8400",  # occupancy_median
        "0.9200",  # occupancy_p75
        "0.9600",  # occupancy_p90
        "0.9800",  # occupancy_max
        "0.8290",  # occupancy_mean
        "0.0642",  # occupancy_stddev
        "0.0",  # probability_full
        "0.35",  # probability_high_occupancy
        "Albert Centre, Block 1",  # development
        "Central",  # area
        "HDB",  # agency
        "500",  # total_lots
        "true",  # has_capacity_data
        "1.3012",  # location_latitude
        "103.8541",  # location_longitude
        "2026-09-04T08:00:00+08:00",  # generated_at
    ]
    csv_content = "\x01".join(raw_row) + "\n"

    mock_s3 = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "level=mart/target=publisher/0000_part_00.csv",
                    "Size": len(csv_content),
                }
            ]
        }
    ]
    mock_s3.get_paginator.return_value = mock_paginator
    mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_content.encode("utf-8"))}

    rows = read_mart_csv_from_s3(
        s3_bucket="test-bucket",
        prefix="level=mart/target=publisher",
        s3_client=mock_s3,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["carpark_id"] == "ACB"
    assert row["lot_type"] == "C"
    assert row["day_of_week"] == 1
    assert row["hour_of_day_sgt"] == 8
    assert row["lots_avail_median"] == 80.0
    assert row["occupancy_median"] == 0.8400
    assert row["is_weekend"] is False
    assert row["has_capacity_data"] is True
    assert row["development"] == "Albert Centre, Block 1"
    assert row["generated_at"] == "2026-09-04T08:00:00+08:00"


@patch("datamart.publisher.read_mart_csv_from_s3")
def test_publish_datamart_to_s3(mock_read):
    """Verifies complete datamart S3 export workflow including manifest and bundle."""
    mock_read.return_value = [
        {
            "carpark_id": "ACB",
            "lot_type": "C",
            "day_of_week": 1,
            "hour_of_day_sgt": 8,
            "observation_count": 60,
            "lots_avail_min": 10.0,
            "lots_avail_p10": 20.0,
            "lots_avail_p25": 40.0,
            "lots_avail_median": 80.0,
            "lots_avail_p75": 120.0,
            "lots_avail_p90": 160.0,
            "lots_avail_max": 200.0,
            "lots_avail_mean": 85.5,
            "lots_avail_stddev": 32.1,
            "lots_occ_min": 300.0,
            "lots_occ_p10": 340.0,
            "lots_occ_p25": 380.0,
            "lots_occ_median": 420.0,
            "lots_occ_p75": 460.0,
            "lots_occ_p90": 480.0,
            "lots_occ_max": 490.0,
            "lots_occ_mean": 414.5,
            "lots_occ_stddev": 32.1,
            "occupancy_min": 0.6000,
            "occupancy_p10": 0.6800,
            "occupancy_p25": 0.7600,
            "occupancy_median": 0.8400,
            "occupancy_p75": 0.9200,
            "occupancy_p90": 0.9600,
            "occupancy_max": 0.9800,
            "occupancy_mean": 0.8290,
            "occupancy_stddev": 0.0642,
            "probability_full": 0.0,
            "probability_high_occupancy": 0.35,
            "development": "Albert Centre",
            "agency": "HDB",
            "total_lots": 500,
            "has_capacity_data": True,
            "location_latitude": 1.3012,
            "location_longitude": 103.8541,
        }
    ]

    mock_s3 = MagicMock()

    result = publish_datamart_to_s3(
        s3_bucket="test-bucket",
        input_prefix="level=mart/target=publisher",
        output_prefix="level=mart/target=downstream",
        version="v1",
        s3_client=mock_s3,
    )

    assert result["status"] == "SUCCESS"
    assert result["carparks_exported"] == 1
    assert result["s3_prefix"] == "level=mart/target=downstream/version=v1"

    # Verify S3 upload calls
    # Should upload: 1 carpark JSON + 1 manifest
    assert mock_s3.put_object.call_count == 2
    keys_uploaded = [call[1]["Key"] for call in mock_s3.put_object.call_args_list]

    assert (
        "level=mart/target=downstream/version=v1/carparks/ACB_C.json" in keys_uploaded
    )
    assert not any("/summary/" in key for key in keys_uploaded)
    assert "level=mart/target=downstream/version=v1/manifest.json" in keys_uploaded


@patch("datamart.handler.publish_datamart_to_s3")
def test_handler_invocation(mock_publish, monkeypatch):
    """Verifies datamart Lambda handler execution with env vars and event payloads."""
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv(
        "INPUT_PREFIX",
        "level=mart/target=publisher/mart_carpark_day_of_week_distribution",
    )
    monkeypatch.setenv("OUTPUT_PREFIX", "level=mart/target=downstream")
    monkeypatch.setenv("DATAMART_VERSION", "v1")
    monkeypatch.setenv("ENV", "prod")

    mock_publish.return_value = {
        "status": "SUCCESS",
        "carparks_exported": 50,
    }

    # Test execution with env vars
    response = handler({}, None)
    assert response["status"] == "SUCCESS"
    assert response["carparks_exported"] == 50
    mock_publish.assert_called_with(
        s3_bucket="test-bucket",
        input_prefix="level=mart/target=publisher/mart_carpark_day_of_week_distribution",
        output_prefix="level=mart/target=downstream",
        version="v1",
    )


def test_handler_raises_when_missing_env_vars(monkeypatch):
    """Verifies datamart Lambda handler strictly errors out when required configs are missing."""
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("INPUT_PREFIX", raising=False)
    monkeypatch.delenv("OUTPUT_PREFIX", raising=False)
    monkeypatch.delenv("DATAMART_VERSION", raising=False)

    with pytest.raises(ValueError, match="S3_BUCKET"):
        handler({}, None)

    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    with pytest.raises(ValueError, match="INPUT_PREFIX"):
        handler({}, None)

    monkeypatch.setenv("INPUT_PREFIX", "level=mart/target=publisher")
    with pytest.raises(ValueError, match="OUTPUT_PREFIX"):
        handler({}, None)

    monkeypatch.setenv("OUTPUT_PREFIX", "level=mart/target=downstream")
    with pytest.raises(ValueError, match="DATAMART_VERSION"):
        handler({}, None)
