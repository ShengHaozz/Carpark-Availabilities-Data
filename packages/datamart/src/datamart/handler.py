"""AWS Lambda entrypoint for publishing the Carpark Availabilities Datamart to S3."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from datamart.publisher import publish_datamart_to_s3
from datamart.schema import DATAMART_API_VERSION

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any] | None = None, context: Any = None) -> Dict[str, Any]:
    """AWS Lambda handler function for datamart publication."""
    logger.info("Starting Carpark Datamart Publisher Lambda...")

    event_dict = event if isinstance(event, dict) else {}
    detail = (
        event_dict.get("detail", {})
        if isinstance(event_dict.get("detail"), dict)
        else {}
    )

    s3_bucket = (
        event_dict.get("s3_bucket")
        or detail.get("s3_bucket")
        or os.environ.get("S3_BUCKET")
    )

    if not s3_bucket:
        logger.error(
            "Missing required S3_BUCKET environment variable or event parameter."
        )
        raise ValueError(
            "S3_BUCKET environment variable or event parameter is required."
        )

    database = (
        event_dict.get("database")
        or detail.get("database")
        or os.environ.get("DATABASE")
    )
    table_name = (
        event_dict.get("table_name")
        or detail.get("table_name")
        or os.environ.get("TABLE_NAME", "mart_carpark_day_of_week_distribution")
    )
    version = (
        event_dict.get("version")
        or detail.get("version")
        or os.environ.get("DATAMART_VERSION", DATAMART_API_VERSION)
    )

    logger.info(
        f"Publishing datamart for bucket='{s3_bucket}', database='{database}', "
        f"table='{table_name}', version='{version}'"
    )

    result = publish_datamart_to_s3(
        s3_bucket=s3_bucket,
        database=database,
        table_name=table_name,
        version=version,
    )

    logger.info(f"Datamart publication finished with result: {result}")
    return result
