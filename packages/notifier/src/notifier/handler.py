import html
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_CAUSE_LENGTH = 1500
TELEGRAM_MESSAGE_LIMIT = 4000


def get_stepfunctions_client(region_name: str | None = None) -> Any:
    return boto3.client("stepfunctions", region_name=region_name)


def extract_failure_details_from_history(
    sfn_client: Any, execution_arn: str
) -> tuple[str | None, str | None, str | None]:
    """Inspects execution history in reverse order to find the failed state name, error, and cause."""
    failed_state: str | None = None
    error_code: str | None = None
    error_cause: str | None = None

    try:
        response = sfn_client.get_execution_history(
            executionArn=execution_arn, reverseOrder=True, maxResults=30
        )
        events = response.get("events", [])

        current_state_name: str | None = None

        for event in events:
            event_type = event.get("type", "")
            event_details = None

            if "StateEntered" in event_type:
                details = event.get("stateEnteredEventDetails", {})
                current_state_name = details.get("name")
                if not failed_state and current_state_name:
                    failed_state = current_state_name

            if "Failed" in event_type or "TimedOut" in event_type:
                # Check task/execution/lambda/activity failure details
                for key in (
                    "taskFailedEventDetails",
                    "executionFailedEventDetails",
                    "lambdaFunctionFailedEventDetails",
                    "activityFailedEventDetails",
                    "executionTimedOutEventDetails",
                ):
                    if key in event:
                        event_details = event[key]
                        break

                if event_details:
                    if not error_code:
                        error_code = event_details.get("error")
                    if not error_cause:
                        error_cause = event_details.get("cause")

            if failed_state and error_code:
                break

    except Exception as e:
        logger.warning(
            "Could not fetch execution history for %s: %s", execution_arn, str(e)
        )

    return failed_state, error_code, error_cause


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "Unknown"
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {sec}s"
    if minutes > 0:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def format_timestamp(dt: datetime | None) -> str:
    if not dt:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_console_url(execution_arn: str, region: str) -> str:
    return f"https://{region}.console.aws.amazon.com/states/home?region={region}#/v2/executions/details/{execution_arn}"


def build_telegram_message(
    state_machine_name: str,
    status: str,
    execution_name: str,
    execution_arn: str,
    region: str,
    duration_str: str,
    timestamp_str: str,
    failed_state: str | None = None,
    error_code: str | None = None,
    error_cause: str | None = None,
) -> str:
    escaped_sm_name = html.escape(state_machine_name)
    escaped_status = html.escape(status)
    escaped_exec_name = html.escape(execution_name)
    console_url = build_console_url(execution_arn, region)

    lines = [
        f"🚨 <b>Step Functions Pipeline Alert</b>",
        "",
        f"<b>Pipeline:</b> <code>{escaped_sm_name}</code>",
        f"<b>Status:</b> <b>{escaped_status}</b>",
        f"<b>Execution:</b> <code>{escaped_exec_name}</code>",
        f"<b>Duration:</b> {duration_str}",
        f"<b>Time:</b> {timestamp_str}",
    ]

    if failed_state:
        lines.append(f"<b>Failed Step:</b> <code>{html.escape(failed_state)}</code>")

    if error_code:
        lines.append(f"<b>Error Type:</b> <code>{html.escape(error_code)}</code>")

    if error_cause:
        cause_clean = error_cause
        # Try to parse if cause is a JSON string with errorMessage / errorType
        try:
            cause_obj = json.loads(error_cause)
            if isinstance(cause_obj, dict):
                cause_clean = cause_obj.get("errorMessage", error_cause)
        except Exception:
            pass

        if len(cause_clean) > MAX_CAUSE_LENGTH:
            cause_clean = cause_clean[:MAX_CAUSE_LENGTH] + "... [truncated]"

        lines.extend([
            "",
            "<b>Error Cause:</b>",
            f"<pre>{html.escape(cause_clean)}</pre>",
        ])

    lines.extend([
        "",
        f'🔗 <a href="{console_url}">Open in AWS Console</a>',
    ])

    message = "\n".join(lines)
    if len(message) > TELEGRAM_MESSAGE_LIMIT:
        message = message[:TELEGRAM_MESSAGE_LIMIT] + "\n... [Message Truncated]"
    return message


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> dict:
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
        logger.error(
            "Telegram API error HTTP %d: %s", e.code, error_body
        )
        raise RuntimeError(f"Telegram API HTTP error {e.code}: {error_body}") from e
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", str(e))
        raise


def handler(event: dict, context: Any = None) -> dict:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    aws_region = os.environ.get("AWS_REGION", "ap-southeast-1")

    if not bot_token or not chat_id:
        raise ValueError(
            "Missing required environment variables: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
        )

    detail = event.get("detail", {})
    status = detail.get("status", "UNKNOWN")
    execution_arn = detail.get("executionArn", "")
    state_machine_arn = detail.get("stateMachineArn", "")
    execution_name = detail.get("name", "Unknown")

    if not execution_arn:
        # Fallback to resources if available
        resources = event.get("resources", [])
        if resources:
            execution_arn = resources[0]

    state_machine_name = (
        state_machine_arn.split(":")[-1]
        if state_machine_arn
        else "Step Functions Pipeline"
    )

    # Calculate duration and timestamps
    start_date_ms = detail.get("startDate")
    stop_date_ms = detail.get("stopDate")
    duration_str = "Unknown"
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if start_date_ms and stop_date_ms:
        duration_sec = (stop_date_ms - start_date_ms) / 1000.0
        duration_str = format_duration(duration_sec)
        timestamp_str = format_timestamp(
            datetime.fromtimestamp(stop_date_ms / 1000.0, tz=timezone.utc)
        )
    elif start_date_ms:
        timestamp_str = format_timestamp(
            datetime.fromtimestamp(start_date_ms / 1000.0, tz=timezone.utc)
        )

    # Query Step Functions for rich execution failure traceback
    sfn_client = get_stepfunctions_client(aws_region)
    failed_state, error_code, error_cause = (None, None, None)

    if execution_arn:
        failed_state, error_code, error_cause = extract_failure_details_from_history(
            sfn_client, execution_arn
        )

    # Fallback to detail error/cause if history didn't populate them
    if not error_code and detail.get("error"):
        error_code = detail.get("error")
    if not error_cause and detail.get("cause"):
        error_cause = detail.get("cause")

    message = build_telegram_message(
        state_machine_name=state_machine_name,
        status=status,
        execution_name=execution_name,
        execution_arn=execution_arn,
        region=aws_region,
        duration_str=duration_str,
        timestamp_str=timestamp_str,
        failed_state=failed_state,
        error_code=error_code,
        error_cause=error_cause,
    )

    logger.info("Sending notification for %s (%s)", state_machine_name, status)
    result = send_telegram_message(bot_token, chat_id, message)

    return {
        "status": "SUCCESS",
        "state_machine": state_machine_name,
        "execution_arn": execution_arn,
        "statusCode": result.get("statusCode", 200),
    }
