import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3

from ..telegram import escape_html, truncate_text
from .registry import register_formatter

logger = logging.getLogger(__name__)

STATUS_TITLES: dict[str, str] = {
    "SUCCEEDED": "Step Functions Pipeline Succeeded",
    "FAILED": "Step Functions Pipeline Failed",
    "TIMED_OUT": "Step Functions Pipeline Timed Out",
    "ABORTED": "Step Functions Pipeline Aborted",
    "RUNNING": "Step Functions Pipeline Started",
}


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

        for event in events:
            event_type = event.get("type", "")
            event_details = None

            if "StateEntered" in event_type:
                details = event.get("stateEnteredEventDetails", {})
                current_state_name = details.get("name")
                if not failed_state and current_state_name:
                    failed_state = current_state_name

            if "Failed" in event_type or "TimedOut" in event_type:
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


@register_formatter("aws.states")
def format_step_functions_event(event: dict[str, Any], region: str) -> str:
    detail = event.get("detail", {})
    status = str(detail.get("status", "UNKNOWN")).upper()
    execution_arn = detail.get("executionArn", "")
    state_machine_arn = detail.get("stateMachineArn", "")
    execution_name = detail.get("name", "Unknown")

    if not execution_arn:
        resources = event.get("resources", [])
        if resources:
            execution_arn = resources[0]

    state_machine_name = (
        state_machine_arn.split(":")[-1]
        if state_machine_arn
        else "Step Functions Pipeline"
    )

    title_text = STATUS_TITLES.get(status, f"Step Functions Pipeline: {status}")

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

    lines = [
        f"<b>{escape_html(title_text)}</b>",
        "",
        f"<b>Pipeline:</b> <code>{escape_html(state_machine_name)}</code>",
        f"<b>Status:</b> <b>{escape_html(status)}</b>",
        f"<b>Execution:</b> <code>{escape_html(execution_name)}</code>",
        f"<b>Duration:</b> {duration_str}",
        f"<b>Time:</b> {timestamp_str}",
    ]

    # For failures, look up failed step and error details
    if status in ("FAILED", "TIMED_OUT", "ABORTED"):
        sfn_client = get_stepfunctions_client(region)
        failed_state, error_code, error_cause = (None, None, None)

        if execution_arn:
            failed_state, error_code, error_cause = extract_failure_details_from_history(
                sfn_client, execution_arn
            )

        if not error_code and detail.get("error"):
            error_code = detail.get("error")
        if not error_cause and detail.get("cause"):
            error_cause = detail.get("cause")

        if failed_state:
            lines.append(f"<b>Failed Step:</b> <code>{escape_html(failed_state)}</code>")

        if error_code:
            lines.append(f"<b>Error Type:</b> <code>{escape_html(error_code)}</code>")

        if error_cause:
            cause_clean = error_cause
            try:
                cause_obj = json.loads(error_cause)
                if isinstance(cause_obj, dict):
                    cause_clean = cause_obj.get("errorMessage", error_cause)
            except Exception:
                pass

            lines.extend([
                "",
                "<b>Error Cause:</b>",
                f"<pre>{escape_html(truncate_text(cause_clean))}</pre>",
            ])

    # If succeeded and output is provided
    elif status == "SUCCEEDED" and detail.get("output"):
        output_str = str(detail.get("output"))
        try:
            parsed = json.loads(output_str)
            output_str = json.dumps(parsed, indent=2)
        except Exception:
            pass

        lines.extend([
            "",
            "<b>Output:</b>",
            f"<pre>{escape_html(truncate_text(output_str))}</pre>",
        ])

    if execution_arn:
        console_url = build_console_url(execution_arn, region)
        lines.extend([
            "",
            f'<a href="{console_url}">Open in AWS Console</a>',
        ])

    return "\n".join(lines)
