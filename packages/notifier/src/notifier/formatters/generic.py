import json
from typing import Any

from ..telegram import escape_html, truncate_text
from .registry import register_fallback_formatter, register_formatter


@register_fallback_formatter
@register_formatter("generic")
def format_generic_event(event: dict[str, Any], region: str) -> str:
    """Fallback formatter for any unknown AWS event or raw JSON payload."""
    source = event.get("source", "Unknown Source")
    detail_type = event.get("detail-type", "Generic Event")
    timestamp = event.get("time", "")

    lines = [
        "<b>System Notification</b>",
        "",
        f"<b>Source:</b> <code>{escape_html(source)}</code>",
        f"<b>Detail Type:</b> <code>{escape_html(detail_type)}</code>",
    ]

    if timestamp:
        lines.append(f"<b>Time:</b> {escape_html(timestamp)}")

    detail = event.get("detail", event)
    try:
        formatted_json = json.dumps(detail, indent=2)
    except Exception:
        formatted_json = str(detail)

    lines.extend([
        "",
        "<b>Payload:</b>",
        f"<pre>{escape_html(truncate_text(formatted_json))}</pre>",
    ])

    return "\n".join(lines)
