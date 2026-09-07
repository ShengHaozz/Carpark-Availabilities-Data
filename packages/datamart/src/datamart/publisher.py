"""S3 integration for directly reading delimited marts and publishing edge-ready JSON files."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import gzip
import io
import json
import logging
from typing import Any, Dict, List, Optional

import boto3

from datamart.exporter import (
    build_carpark_documents,
    dump_carpark_document_json,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Column names in physical order from mart_carpark_day_of_week_distribution model
MART_COLUMNS = [
    "distribution_id",
    "carpark_id",
    "lot_type",
    "day_of_week",
    "day_name",
    "is_weekend",
    "hour_of_day_sgt",
    "observation_count",
    "lots_avail_min",
    "lots_avail_p10",
    "lots_avail_p25",
    "lots_avail_median",
    "lots_avail_p75",
    "lots_avail_p90",
    "lots_avail_max",
    "lots_avail_mean",
    "lots_avail_stddev",
    "lots_occ_min",
    "lots_occ_p10",
    "lots_occ_p25",
    "lots_occ_median",
    "lots_occ_p75",
    "lots_occ_p90",
    "lots_occ_max",
    "lots_occ_mean",
    "lots_occ_stddev",
    "occupancy_min",
    "occupancy_p10",
    "occupancy_p25",
    "occupancy_median",
    "occupancy_p75",
    "occupancy_p90",
    "occupancy_max",
    "occupancy_mean",
    "occupancy_stddev",
    "probability_full",
    "probability_high_occupancy",
    "development",
    "area",
    "agency",
    "total_lots",
    "has_capacity_data",
    "location_latitude",
    "location_longitude",
    "generated_at",
]

# Numerical columns expected from mart_carpark_day_of_week_distribution
FLOAT_COLUMNS = {
    "lots_avail_min",
    "lots_avail_p10",
    "lots_avail_p25",
    "lots_avail_median",
    "lots_avail_p75",
    "lots_avail_p90",
    "lots_avail_max",
    "lots_avail_mean",
    "lots_avail_stddev",
    "lots_occ_min",
    "lots_occ_p10",
    "lots_occ_p25",
    "lots_occ_median",
    "lots_occ_p75",
    "lots_occ_p90",
    "lots_occ_max",
    "lots_occ_mean",
    "lots_occ_stddev",
    "occupancy_min",
    "occupancy_p10",
    "occupancy_p25",
    "occupancy_median",
    "occupancy_p75",
    "occupancy_p90",
    "occupancy_max",
    "occupancy_mean",
    "occupancy_stddev",
    "probability_full",
    "probability_high_occupancy",
    "location_latitude",
    "location_longitude",
}

INT_COLUMNS = {
    "day_of_week",
    "hour_of_day_sgt",
    "observation_count",
    "total_lots",
}

BOOL_COLUMNS = {
    "is_weekend",
    "has_capacity_data",
}

# Hive TEXTFILE does not CSV-quote values, so commas in carpark metadata would
# otherwise shift columns. This must match the dbt `field_delimiter` setting.
MART_FIELD_DELIMITER = "\x01"
CARPARK_INITIALS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ("OTHER",)


def parse_csv_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Casts raw CSV string values into typed dictionary fields."""
    typed_row: Dict[str, Any] = {}
    for col, val in row_dict.items():
        if val is None or val == "" or str(val).lower() == "null":
            typed_row[col] = None
        elif col in FLOAT_COLUMNS:
            try:
                typed_row[col] = float(val)
            except (ValueError, TypeError):
                typed_row[col] = None
        elif col in INT_COLUMNS:
            try:
                typed_row[col] = int(val)
            except (ValueError, TypeError):
                typed_row[col] = None
        elif col in BOOL_COLUMNS:
            typed_row[col] = str(val).lower() in ("true", "1", "t")
        else:
            typed_row[col] = val
    return typed_row


def read_mart_csv_from_s3(
    s3_bucket: str,
    prefix: str,
    s3_client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Lists and streams CSV data files directly from S3 without Athena."""
    client = s3_client or boto3.client("s3")
    list_prefix = f"{prefix}/"

    logger.info(f"Listing CSV files from s3://{s3_bucket}/{list_prefix}...")
    paginator = client.get_paginator("list_objects_v2")
    records: List[Dict[str, Any]] = []

    for page in paginator.paginate(Bucket=s3_bucket, Prefix=list_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Ignore directory markers, zero-size files, or Athena metadata
            if key.endswith("/") or obj.get("Size", 0) == 0 or "$folder$" in key:
                continue

            logger.info(f"Streaming mart data from s3://{s3_bucket}/{key}...")
            response = client.get_object(Bucket=s3_bucket, Key=key)
            body = response["Body"].read()

            # Handle possible gzip compression
            if key.endswith(".gz") or (len(body) >= 2 and body[:2] == b"\x1f\x8b"):
                content = gzip.decompress(body).decode("utf-8")
            else:
                content = body.decode("utf-8")

            csv_stream = io.StringIO(content)
            first_line = csv_stream.readline()
            if not first_line:
                continue
            csv_stream.seek(0)

            # Detect whether header row is present
            has_header = "carpark_id" in first_line

            if has_header:
                dict_reader = csv.DictReader(csv_stream, delimiter=MART_FIELD_DELIMITER)
                for row_dict in dict_reader:
                    records.append(parse_csv_row(row_dict))
            else:
                plain_reader = csv.reader(csv_stream, delimiter=MART_FIELD_DELIMITER)
                for row in plain_reader:
                    if not row or all(c == "" for c in row):
                        continue
                    row_dict = {
                        MART_COLUMNS[i]: row[i]
                        for i in range(min(len(row), len(MART_COLUMNS)))
                    }
                    records.append(parse_csv_row(row_dict))

    logger.info(f"Loaded and type-cast {len(records)} total records from S3 mart CSVs.")
    return records


def _upload_single_carpark_json(
    s3_client: Any,
    s3_bucket: str,
    s3_key: str,
    json_str: str,
) -> None:
    """Uploads a single carpark JSON file to S3 with cache-control headers."""
    s3_client.put_object(
        Bucket=s3_bucket,
        Key=s3_key,
        Body=json_str.encode("utf-8"),
        ContentType="application/json",
        CacheControl="public, max-age=86400",
    )


def publish_datamart_to_s3(
    s3_bucket: str,
    input_prefix: str,
    output_prefix: str,
    version: str,
    max_workers: int = 20,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Directly reads CSV mart from S3 and publishes JSON files and GZIP bundles to S3."""
    client_s3 = s3_client or boto3.client("s3")

    logger.info(
        f"Starting datamart publication for s3://{s3_bucket}/{input_prefix} -> {output_prefix} (version={version})..."
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    prefix = f"{output_prefix}/version={version}"
    uploaded_count = 0
    manifest_carparks: List[Dict[str, Any]] = []

    for carpark_initial in CARPARK_INITIALS:
        logger.info("Processing carpark_initial=%s", carpark_initial)
        rows = read_mart_csv_from_s3(
            s3_bucket=s3_bucket,
            prefix=f"{input_prefix}/carpark_initial={carpark_initial}",
            s3_client=client_s3,
        )
        if not rows:
            continue

        documents = build_carpark_documents(rows, generated_at=now_iso)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _upload_single_carpark_json,
                    client_s3,
                    s3_bucket,
                    f"{prefix}/carparks/{doc.carpark.carpark_id}_{doc.carpark.lot_type}.json",
                    dump_carpark_document_json(doc),
                ): doc
                for doc in documents
            }
            for future in as_completed(futures):
                future.result()
                uploaded_count += 1

        manifest_carparks.extend(
            {
                "carpark_id": doc.carpark.carpark_id,
                "lot_type": doc.carpark.lot_type,
                "agency": doc.carpark.agency,
                "development": doc.carpark.development,
                "has_capacity_data": doc.carpark.has_capacity_data,
                "file_path": f"carparks/{doc.carpark.carpark_id}_{doc.carpark.lot_type}.json",
            }
            for doc in documents
        )
        logger.info(
            "Published %d documents for carpark_initial=%s",
            len(documents),
            carpark_initial,
        )

    if not manifest_carparks:
        logger.warning(f"No rows found in partitioned S3 mart prefix '{input_prefix}'.")
        return {"status": "SKIPPED", "reason": "Empty dataset", "carparks_exported": 0}

    # 2. Upload metadata manifest
    manifest_key = f"{prefix}/manifest.json"
    manifest_data = {
        "version": version,
        "generated_at": now_iso,
        "total_carparks": uploaded_count,
        "endpoints": {
            "carpark_template": f"/{prefix}/carparks/{{carpark_id}}_{{lot_type}}.json",
        },
        "carparks": manifest_carparks,
    }
    client_s3.put_object(
        Bucket=s3_bucket,
        Key=manifest_key,
        Body=json.dumps(manifest_data, indent=2).encode("utf-8"),
        ContentType="application/json",
        CacheControl="public, max-age=86400",
    )
    logger.info(f"Uploaded datamart manifest to s3://{s3_bucket}/{manifest_key}.")

    return {
        "status": "SUCCESS",
        "carparks_exported": uploaded_count,
        "s3_prefix": prefix,
        "manifest_key": manifest_key,
    }
