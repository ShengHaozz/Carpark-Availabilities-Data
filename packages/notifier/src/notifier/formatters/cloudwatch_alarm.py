from typing import Any

from ..telegram import escape_html, truncate_text
from .registry import register_formatter


@register_formatter("aws.cloudwatch", "aws.alarm")
def format_cloudwatch_alarm_event(event: dict[str, Any], region: str) -> str:
    """Formats AWS CloudWatch Alarm state change events."""
    detail = event.get("detail", {})
    alarm_name = detail.get("alarmName", "Unknown Alarm")
    state = detail.get("state", {})
    new_state = state.get("value", detail.get("newStateValue", "UNKNOWN"))
    previous_state = detail.get("previousStateValue", "UNKNOWN")
    reason = state.get("reason", detail.get("stateReason", "No reason provided"))
    timestamp = event.get("time", "")

    lines = [
        "<b>CloudWatch Alarm Alert</b>",
        "",
        f"<b>Alarm:</b> <code>{escape_html(alarm_name)}</code>",
        f"<b>State:</b> <b>{escape_html(new_state)}</b> (was {escape_html(previous_state)})",
    ]

    if timestamp:
        lines.append(f"<b>Time:</b> {escape_html(timestamp)}")

    if reason:
        lines.extend([
            "",
            "<b>Reason:</b>",
            f"<pre>{escape_html(truncate_text(reason))}</pre>",
        ])

    console_url = f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#alarmsV2:alarm/{alarm_name}"
    lines.extend([
        "",
        f'<a href="{console_url}">Open Alarm in AWS Console</a>',
    ])

    return "\n".join(lines)
