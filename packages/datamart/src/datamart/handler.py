"""AWS Lambda entrypoint for publishing the Carpark Availabilities Datamart to S3."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from datamart.publisher import publish_datamart_to_s3

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

    input_prefix = (
        event_dict.get("input_prefix")
        or detail.get("input_prefix")
        or os.environ.get("INPUT_PREFIX")
    )
    if not input_prefix:
        logger.error(
            "Missing required INPUT_PREFIX environment variable or event parameter."
        )
        raise ValueError(
            "INPUT_PREFIX environment variable or event parameter is required."
        )

    output_prefix = (
        event_dict.get("output_prefix")
        or detail.get("output_prefix")
        or os.environ.get("OUTPUT_PREFIX")
    )
    if not output_prefix:
        logger.error(
            "Missing required OUTPUT_PREFIX environment variable or event parameter."
        )
        raise ValueError(
            "OUTPUT_PREFIX environment variable or event parameter is required."
        )

    version = (
        event_dict.get("version")
        or detail.get("version")
        or os.environ.get("DATAMART_VERSION")
    )
    if not version:
        logger.error(
            "Missing required DATAMART_VERSION environment variable or event parameter."
        )
        raise ValueError(
            "DATAMART_VERSION environment variable or event parameter is required."
        )

    logger.info(
        f"Publishing datamart for bucket='{s3_bucket}', input_prefix='{input_prefix}', "
        f"output_prefix='{output_prefix}', version='{version}'"
    )

    result = publish_datamart_to_s3(
        s3_bucket=s3_bucket,
        input_prefix=input_prefix,
        output_prefix=output_prefix,
        version=version,
    )

    logger.info(f"Datamart publication finished with result: {result}")
    return result
