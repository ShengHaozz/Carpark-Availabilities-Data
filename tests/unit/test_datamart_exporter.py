"""Unit tests for Carpark JSON Datamart schema and serialization exporter."""

import gzip
import json
from typing import Any, Dict, List

from gold.exporter import (
    serialize_carpark_document_json,
    serialize_documents_bundle_gzip,
    transform_mart_records_to_documents,
)


def _sample_hdb_mart_rows() -> List[Dict[str, Any]]:
    """Generates mock mart records for an HDB carpark with known capacity."""
    rows = []
    # Generate for Day 1 (Monday), hours 8 and 9
    for hr in [8, 9]:
        rows.append(
            {
                "distribution_id": f"ACB_C_1_{hr}",
                "carpark_id": "ACB",
                "lot_type": "C",
                "day_of_week": 1,
                "day_name": "Monday",
                "is_weekend": False,
                "hour_of_day_sgt": hr,
                "observation_count": 60,
                # Available lots
                "lots_avail_min": 10.0,
                "lots_avail_p10": 20.0,
                "lots_avail_p25": 40.0,
                "lots_avail_median": 80.0,
                "lots_avail_p75": 120.0,
                "lots_avail_p90": 160.0,
                "lots_avail_max": 200.0,
                "lots_avail_mean": 85.5,
                "lots_avail_stddev": 32.1,
                # Occupied lots
                "lots_occ_min": 300.0,
                "lots_occ_p10": 340.0,
                "lots_occ_p25": 380.0,
                "lots_occ_median": 420.0,
                "lots_occ_p75": 460.0,
                "lots_occ_p90": 480.0,
                "lots_occ_max": 490.0,
                "lots_occ_mean": 414.5,
                "lots_occ_stddev": 32.1,
                # Occupancy rate
                "occupancy_min": 0.6000,
                "occupancy_p10": 0.6800,
                "occupancy_p25": 0.7600,
                "occupancy_median": 0.8400,
                "occupancy_p75": 0.9200,
                "occupancy_p90": 0.9600,
                "occupancy_max": 0.9800,
                "occupancy_mean": 0.8290,
                "occupancy_stddev": 0.0642,
                # Probabilities
                "probability_full": 0.0000,
                "probability_high_occupancy": 0.3500,
                # Metadata
                "development": "BLOCK 270/271 ALBERT CENTRE BASEMENT CAR PARK",
                "area": "Bencoolen",
                "agency": "HDB",
                "total_lots": 500,
                "has_capacity_data": True,
                "location_latitude": 1.30123,
                "location_longitude": 103.85412,
            }
        )
    return rows


def _sample_non_hdb_mart_rows() -> List[Dict[str, Any]]:
    """Generates mock mart records for a non-HDB carpark without known capacity."""
    rows = []
    for hr in [12, 13]:
        rows.append(
            {
                "distribution_id": f"SUNTEC_C_1_{hr}",
                "carpark_id": "SUNTEC",
                "lot_type": "C",
                "day_of_week": 1,
                "day_name": "Monday",
                "is_weekend": False,
                "hour_of_day_sgt": hr,
                "observation_count": 60,
                # Available lots
                "lots_avail_min": 50.0,
                "lots_avail_p10": 120.0,
                "lots_avail_p25": 250.0,
                "lots_avail_median": 450.0,
                "lots_avail_p75": 700.0,
                "lots_avail_p90": 950.0,
                "lots_avail_max": 1200.0,
                "lots_avail_mean": 480.2,
                "lots_avail_stddev": 210.5,
                # Occupied lots & Occupancy (None for non-HDB)
                "lots_occ_min": None,
                "lots_occ_p10": None,
                "lots_occ_p25": None,
                "lots_occ_median": None,
                "lots_occ_p75": None,
                "lots_occ_p90": None,
                "lots_occ_max": None,
                "lots_occ_mean": None,
                "lots_occ_stddev": None,
                "occupancy_min": None,
                "occupancy_p10": None,
                "occupancy_p25": None,
                "occupancy_median": None,
                "occupancy_p75": None,
                "occupancy_p90": None,
                "occupancy_max": None,
                "occupancy_mean": None,
                "occupancy_stddev": None,
                # Probabilities
                "probability_full": 0.0150,
                "probability_high_occupancy": None,
                # Metadata
                "development": "Suntec City Mall",
                "area": "Marina",
                "agency": "LTA",
                "total_lots": None,
                "has_capacity_data": False,
                "location_latitude": 1.29340,
                "location_longitude": 103.85720,
            }
        )
    return rows


def test_hdb_carpark_transformation():
    """Verifies complete contract generation for HDB carparks with capacity."""
    raw_rows = _sample_hdb_mart_rows()
    documents = transform_mart_records_to_documents(
        raw_rows, generated_at="2026-09-02T00:15:00+08:00"
    )

    assert "ACB_C" in documents
    doc = documents["ACB_C"]

    # Carpark Metadata assertions
    assert doc.carpark.carpark_id == "ACB"
    assert doc.carpark.lot_type == "C"
    assert doc.carpark.lot_type_description == "Cars"
    assert doc.carpark.agency == "HDB"
    assert doc.carpark.total_lots == 500
    assert doc.carpark.has_capacity_data is True
    assert doc.carpark.coordinates is not None
    assert doc.carpark.coordinates.latitude == 1.30123
    assert doc.carpark.coordinates.longitude == 103.85412

    # Weekly distribution structure
    assert len(doc.weekly_distribution) == 7
    mon = doc.weekly_distribution["1"]
    assert mon.day_name == "Monday"
    assert mon.day_of_week == 1
    assert mon.is_weekend is False

    # Hourly distribution assertions
    assert len(mon.hourly_distribution) == 2
    h8 = mon.hourly_distribution[0]
    assert h8.hour_of_day_sgt == 8
    assert h8.time_window == "08:00 - 08:59"
    assert h8.observation_count == 60
    assert h8.lots_available.p50 == 80.0
    assert h8.occupancy_rate is not None
    assert h8.occupancy_rate.p50 == 0.8400
    assert h8.probability_high_occupancy_ge_90pct == 0.3500


def test_non_hdb_carpark_transformation():
    """Verifies non-HDB carparks without capacity emit null occupancy metrics cleanly."""
    raw_rows = _sample_non_hdb_mart_rows()
    documents = transform_mart_records_to_documents(
        raw_rows, generated_at="2026-09-02T00:15:00+08:00"
    )

    assert "SUNTEC_C" in documents
    doc = documents["SUNTEC_C"]

    # Carpark Metadata assertions
    assert doc.carpark.carpark_id == "SUNTEC"
    assert doc.carpark.agency == "LTA"
    assert doc.carpark.total_lots is None
    assert doc.carpark.has_capacity_data is False

    # Hourly distribution assertions
    mon = doc.weekly_distribution["1"]
    assert len(mon.hourly_distribution) == 2
    h12 = mon.hourly_distribution[0]
    assert h12.hour_of_day_sgt == 12
    assert h12.lots_available.p50 == 450.0
    assert h12.occupancy_rate is None
    assert h12.lots_occupied is None
    assert h12.probability_full == 0.0150
    assert h12.probability_high_occupancy_ge_90pct is None


def test_json_serialization_fidelity():
    """Verifies that serialized JSON matches JSON Schema expectations and preserves $schema."""
    raw_rows = _sample_hdb_mart_rows()
    documents = transform_mart_records_to_documents(raw_rows)
    doc = documents["ACB_C"]

    json_str = serialize_carpark_document_json(doc)
    parsed = json.loads(json_str)

    assert "$schema" in parsed
    assert parsed["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert parsed["carpark"]["carpark_id"] == "ACB"
    assert parsed["carpark"]["has_capacity_data"] is True
    assert "weekly_distribution" in parsed
    assert "1" in parsed["weekly_distribution"]


def test_gzipped_bundle_serialization():
    """Verifies consolidated GZIP bundle creation and contents."""
    hdb_rows = _sample_hdb_mart_rows()
    non_hdb_rows = _sample_non_hdb_mart_rows()
    documents = transform_mart_records_to_documents(hdb_rows + non_hdb_rows)

    assert len(documents) == 2
    gzip_bytes = serialize_documents_bundle_gzip(documents)

    decompressed = gzip.decompress(gzip_bytes).decode("utf-8")
    parsed_bundle = json.loads(decompressed)

    assert parsed_bundle["metadata"]["total_carparks"] == 2
    assert len(parsed_bundle["carparks"]) == 2
