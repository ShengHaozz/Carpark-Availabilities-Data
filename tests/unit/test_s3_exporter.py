"""Unit tests for datamart.publisher and datamart.handler modules."""

import io
from unittest.mock import MagicMock, patch
import pytest

from datamart.handler import handler
from datamart.publisher import (
    _parse_s3_url,
    fetch_query_results_from_s3,
    publish_datamart_to_s3,
    run_athena_query,
)


def test_parse_s3_url():
    """Verifies parsing of various s3:// URL formats."""
    bucket, prefix = _parse_s3_url("s3://my-bucket/athena-query-results/")
    assert bucket == "my-bucket"
    assert prefix == "athena-query-results/"

    bucket, prefix = _parse_s3_url("s3://my-bucket/data/file.csv")
    assert bucket == "my-bucket"
    assert prefix == "data/file.csv"


def test_run_athena_query_success():
    """Verifies successful Athena query submission and polling."""
    mock_athena = MagicMock()
    mock_athena.start_query_execution.return_value = {
        "QueryExecutionId": "test-query-123"
    }
    mock_athena.get_query_execution.return_value = {
        "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
    }

    query_id = run_athena_query(
        query="SELECT * FROM mart",
        database="prod_marts",
        s3_staging_dir="s3://test-bucket/athena-results/",
        athena_client=mock_athena,
        poll_interval_sec=0.01,
    )

    assert query_id == "test-query-123"
    mock_athena.start_query_execution.assert_called_once()
    mock_athena.get_query_execution.assert_called_once_with(
        QueryExecutionId="test-query-123"
    )


def test_run_athena_query_failure():
    """Verifies that an Athena query failure raises RuntimeError."""
    mock_athena = MagicMock()
    mock_athena.start_query_execution.return_value = {
        "QueryExecutionId": "test-query-fail"
    }
    mock_athena.get_query_execution.return_value = {
        "QueryExecution": {
            "Status": {
                "State": "FAILED",
                "StateChangeReason": "Syntax error in SQL statement",
            }
        }
    }

    with pytest.raises(RuntimeError, match="Syntax error in SQL statement"):
        run_athena_query(
            query="SELECT * FROM invalid",
            database="prod_marts",
            s3_staging_dir="s3://test-bucket/athena-results/",
            athena_client=mock_athena,
            poll_interval_sec=0.01,
        )


def test_fetch_query_results_from_s3():
    """Verifies reading and type casting of CSV results from S3."""
    csv_content = (
        "carpark_id,lot_type,day_of_week,hour_of_day_sgt,observation_count,"
        "lots_avail_min,lots_avail_median,occupancy_median,is_weekend,has_capacity_data,agency\n"
        "ACB,C,1,8,60,10.0,80.0,0.8400,false,true,HDB\n"
        "SUNTEC,C,1,12,60,50.0,450.0,,false,false,LTA\n"
    )

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_content.encode("utf-8"))}

    rows = fetch_query_results_from_s3(
        query_execution_id="test-query-123",
        s3_staging_dir="s3://test-bucket/athena-query-results/",
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


@patch("datamart.publisher.run_athena_query")
@patch("datamart.publisher.fetch_query_results_from_s3")
def test_publish_datamart_to_s3(mock_fetch, mock_query):
    """Verifies complete datamart S3 export workflow including manifest and bundle."""
    mock_query.return_value = "query-abc"
    mock_fetch.return_value = [
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
    mock_athena = MagicMock()

    result = publish_datamart_to_s3(
        s3_bucket="test-bucket",
        database="prod_marts",
        version="v1",
        s3_client=mock_s3,
        athena_client=mock_athena,
    )

    assert result["status"] == "SUCCESS"
    assert result["carparks_exported"] == 1
    assert result["s3_prefix"] == "level=datamart/version=v1"

    # Verify S3 upload calls
    # Should upload: 1 carpark JSON + 1 gzip bundle + 1 manifest
    assert mock_s3.put_object.call_count == 3
    keys_uploaded = [call[1]["Key"] for call in mock_s3.put_object.call_args_list]

    assert "level=datamart/version=v1/carparks/ACB_C.json" in keys_uploaded
    assert (
        "level=datamart/version=v1/summary/weekly_carpark_distributions.json.gz"
        in keys_uploaded
    )
    assert "level=datamart/version=v1/manifest.json" in keys_uploaded


@patch("datamart.handler.publish_datamart_to_s3")
def test_handler_invocation(mock_publish, monkeypatch):
    """Verifies datamart Lambda handler execution with env vars and event payloads."""
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("ENV", "prod")

    mock_publish.return_value = {
        "status": "SUCCESS",
        "carparks_exported": 50,
    }

    # Test event-based execution
    response = handler({"table_name": "mart_custom"}, None)
    assert response["status"] == "SUCCESS"
    assert response["carparks_exported"] == 50
    mock_publish.assert_called_with(
        s3_bucket="test-bucket",
        database=None,
        table_name="mart_custom",
        version="v1",
    )
