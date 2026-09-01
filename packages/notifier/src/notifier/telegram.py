import html
import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4000
MAX_PRE_BLOCK_LENGTH = 1500


def escape_html(text: str | None) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def truncate_text(text: str | None, max_len: int = MAX_PRE_BLOCK_LENGTH) -> str:
    if not text:
        return ""
    if len(text) > max_len:
        return text[:max_len] + "... [truncated]"
    return text


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> dict[str, Any]:
    if len(message) > TELEGRAM_MESSAGE_LIMIT:
        message = message[:TELEGRAM_MESSAGE_LIMIT] + "\n... [Message Truncated]"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            return {
                "statusCode": response.status,
                "response": json.loads(res_body) if res_body else {},
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error("Telegram API error HTTP %d: %s", e.code, error_body)
        raise RuntimeError(f"Telegram API HTTP error {e.code}: {error_body}") from e
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", str(e))
        raise
