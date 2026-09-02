import logging
import os
from typing import Any

from .formatters import get_formatter
from .telegram import send_telegram_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    aws_region = os.environ.get("AWS_REGION", "ap-southeast-1")

    if not bot_token or not chat_id:
        raise ValueError(
            "Missing required environment variables: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
        )

    # Resolve appropriate formatter based on event structure and source
    formatter = get_formatter(event)
    source = event.get("source", "direct/custom")

    logger.info("Formatting notification for source '%s' using %s", source, formatter.__name__)
    message = formatter(event, aws_region)

    result = send_telegram_message(bot_token, chat_id, message)

    return {
        "status": "SUCCESS",
        "source": source,
        "statusCode": result.get("statusCode", 200),
    }
