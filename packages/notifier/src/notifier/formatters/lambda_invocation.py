import json
from typing import Any
from urllib.parse import quote

from ..telegram import escape_html, truncate_text
from .registry import register_formatter


def _function_name(function_arn: str) -> str:
    """Returns an unqualified Lambda function name from an ARN."""
    if ":function:" not in function_arn:
        return function_arn or "Unknown"
    return function_arn.split(":function:", 1)[1].split(":", 1)[0]


def _format_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, indent=2)
    except (TypeError, ValueError):
        return str(payload)


@register_formatter("lambda")
def format_lambda_invocation_event(event: dict[str, Any], region: str) -> str:
    """Formats Lambda asynchronous invocation result events for Telegram."""
    detail = event.get("detail", {})
    request_context = detail.get("requestContext", {})
    response_context = detail.get("responseContext", {})
    detail_type = str(event.get("detail-type", ""))

    condition = str(request_context.get("condition", "Unknown"))
    is_success = "Success" in detail_type or condition == "Success"
    title = "Lambda Invocation Succeeded" if is_success else "Lambda Invocation Failed"

    function_arn = str(request_context.get("functionArn", ""))
    function_name = _function_name(function_arn)
    attempt = request_context.get("approximateInvokeCount")
    status_code = response_context.get("statusCode")

    lines = [
        f"<b>{title}</b>",
        "",
        f"<b>Function:</b> <code>{escape_html(function_name)}</code>",
        f"<b>Status:</b> <b>{escape_html(condition)}</b>",
    ]

    if attempt is not None:
        lines.append(f"<b>Attempt:</b> {escape_html(str(attempt))}")
    if status_code is not None:
        lines.append(f"<b>Response Status:</b> {escape_html(str(status_code))}")
    if event.get("time"):
        lines.append(f"<b>Time:</b> {escape_html(str(event['time']))}")

    response_payload = detail.get("responsePayload")
    if not is_success and response_payload is not None:
        lines.extend([
            "",
            "<b>Error:</b>",
            f"<pre>{escape_html(truncate_text(_format_payload(response_payload)))}</pre>",
        ])

    if function_name != "Unknown":
        console_url = (
            f"https://{region}.console.aws.amazon.com/lambda/home?region={region}"
            f"#/functions/{quote(function_name, safe='')}?tab=monitoring"
        )
        lines.extend(["", f'<a href="{console_url}">Open in AWS Console</a>'])

    return "\n".join(lines)
