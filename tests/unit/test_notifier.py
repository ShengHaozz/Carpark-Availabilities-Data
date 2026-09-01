import json
import urllib.error
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from packages.notifier.src.notifier.formatters.cloudwatch_alarm import (
    format_cloudwatch_alarm_event,
)
from packages.notifier.src.notifier.formatters.generic import format_generic_event
from packages.notifier.src.notifier.formatters.registry import (
    get_formatter,
    register_formatter,
)
from packages.notifier.src.notifier.formatters.step_functions import (
    build_console_url,
    extract_failure_details_from_history,
    format_duration,
    format_step_functions_event,
    format_timestamp,
)
from packages.notifier.src.notifier.handler import handler
from packages.notifier.src.notifier.telegram import (
    escape_html,
    send_telegram_message,
    truncate_text,
)


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123456789")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")


@pytest.fixture
def sample_sfn_failed_event():
    return {
        "version": "0",
        "id": "e83e6024-814a-7bc9-5567-0c6a49c30e46",
        "detail-type": "Step Functions Execution Status Change",
        "source": "aws.states",
        "account": "123456789012",
        "time": "2026-08-31T01:00:00Z",
        "region": "ap-southeast-1",
        "resources": [
            "arn:aws:states:ap-southeast-1:123456789012:execution:carpark-daily-pipeline:exec-123"
        ],
        "detail": {
            "executionArn": "arn:aws:states:ap-southeast-1:123456789012:execution:carpark-daily-pipeline:exec-123",
            "stateMachineArn": "arn:aws:states:ap-southeast-1:123456789012:stateMachine:carpark-daily-pipeline",
            "name": "exec-123",
            "status": "FAILED",
            "startDate": 1756598400000,
            "stopDate": 1756598525000,
        },
    }


def test_handler_missing_env_vars(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValueError, match="Missing required environment variables"):
        handler({"detail": {}})


# --- Step Functions Formatter Tests ---


def test_extract_failure_details_from_history():
    mock_sfn = MagicMock()
    mock_sfn.get_execution_history.return_value = {
        "events": [
            {
                "type": "ExecutionFailed",
                "executionFailedEventDetails": {
                    "error": "CustomPipelineError",
                    "cause": json.dumps({"errorMessage": "Silver cold transformation failed"}),
                },
            },
            {
                "type": "TaskFailed",
                "taskFailedEventDetails": {
                    "error": "Lambda.Unknown",
                    "cause": "Process crashed",
                },
            },
            {
                "type": "TaskStateEntered",
                "stateEnteredEventDetails": {
                    "name": "TransformSilver",
                },
            },
        ]
    }

    state, error, cause = extract_failure_details_from_history(mock_sfn, "arn:aws:states:exec-1")
    assert state == "TransformSilver"
    assert error == "CustomPipelineError"
    assert "Silver cold transformation failed" in (cause or "")


def test_extract_failure_details_with_exception():
    mock_sfn = MagicMock()
    mock_sfn.get_execution_history.side_effect = Exception("Access Denied")

    state, error, cause = extract_failure_details_from_history(mock_sfn, "arn:aws:states:exec-1")
    assert state is None
    assert error is None
    assert cause is None


def test_format_duration():
    assert format_duration(None) == "Unknown"
    assert format_duration(45) == "45s"
    assert format_duration(125) == "2m 5s"
    assert format_duration(3665) == "1h 1m 5s"


def test_format_timestamp():
    dt = datetime(2026, 8, 31, 1, 0, 0, tzinfo=timezone.utc)
    assert format_timestamp(dt) == "2026-08-31 01:00:00 UTC"
    assert "UTC" in format_timestamp(None)


def test_build_console_url():
    url = build_console_url("arn:aws:states:ap-southeast-1:123:execution:sm:e1", "ap-southeast-1")
    assert "ap-southeast-1.console.aws.amazon.com" in url
    assert "arn:aws:states:ap-southeast-1:123:execution:sm:e1" in url


@patch("packages.notifier.src.notifier.formatters.step_functions.get_stepfunctions_client")
def test_format_step_functions_event(mock_get_sfn, sample_sfn_failed_event):
    mock_sfn = MagicMock()
    mock_sfn.get_execution_history.return_value = {
        "events": [
            {
                "type": "TaskStateEntered",
                "stateEnteredEventDetails": {"name": "Transform<Silver>"},
            },
            {
                "type": "TaskFailed",
                "taskFailedEventDetails": {
                    "error": "Error&Fail",
                    "cause": "<script>alert('xss')</script>",
                },
            },
        ]
    }
    mock_get_sfn.return_value = mock_sfn

    msg = format_step_functions_event(sample_sfn_failed_event, "ap-southeast-1")
    assert "carpark-daily-pipeline" in msg
    assert "Step Functions Pipeline Failed" in msg
    assert "Transform&lt;Silver&gt;" in msg
    assert "&lt;script&gt;" in msg
    assert "<script>" not in msg
    assert "Open in AWS Console" in msg


def test_format_step_functions_event_succeeded():
    event = {
        "source": "aws.states",
        "detail": {
            "executionArn": "arn:aws:states:ap-southeast-1:123:execution:carpark-daily-pipeline:exec-456",
            "stateMachineArn": "arn:aws:states:ap-southeast-1:123:stateMachine:carpark-daily-pipeline",
            "name": "exec-456",
            "status": "SUCCEEDED",
            "startDate": 1756598400000,
            "stopDate": 1756598500000,
            "output": json.dumps({"status": "SUCCESS", "rows_processed": 1000}),
        },
    }

    msg = format_step_functions_event(event, "ap-southeast-1")
    assert "Step Functions Pipeline Succeeded" in msg
    assert "carpark-daily-pipeline" in msg
    assert "1m 40s" in msg
    assert "rows_processed" in msg
    assert "Open in AWS Console" in msg


def test_format_step_functions_event_running():
    event = {
        "source": "aws.states",
        "detail": {
            "executionArn": "arn:aws:states:ap-southeast-1:123:execution:carpark-daily-pipeline:exec-789",
            "stateMachineArn": "arn:aws:states:ap-southeast-1:123:stateMachine:carpark-daily-pipeline",
            "name": "exec-789",
            "status": "RUNNING",
            "startDate": 1756598400000,
        },
    }

    msg = format_step_functions_event(event, "ap-southeast-1")
    assert "Step Functions Pipeline Started" in msg
    assert "carpark-daily-pipeline" in msg


# --- CloudWatch Alarm Formatter Tests ---


def test_format_cloudwatch_alarm_event():
    alarm_event = {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "time": "2026-08-31T02:00:00Z",
        "detail": {
            "alarmName": "HighLambdaErrorRate",
            "state": {
                "value": "ALARM",
                "reason": "Threshold Crossed: 1 out of 1 datapoints was greater than 5.",
            },
            "previousStateValue": "OK",
        },
    }

    msg = format_cloudwatch_alarm_event(alarm_event, "ap-southeast-1")
    assert "CloudWatch Alarm Alert" in msg
    assert "HighLambdaErrorRate" in msg
    assert "ALARM" in msg
    assert "Threshold Crossed" in msg


# --- Generic Fallback Formatter Tests ---


def test_format_generic_event():
    event = {
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {"bucket": "my-bucket", "key": "test.json"},
    }

    msg = format_generic_event(event, "ap-southeast-1")
    assert "System Notification" in msg
    assert "aws.s3" in msg
    assert "my-bucket" in msg


# --- Formatter Registry Tests ---


def test_registry_resolution():
    assert get_formatter({"source": "aws.states"}) == format_step_functions_event
    assert get_formatter({"source": "aws.cloudwatch"}) == format_cloudwatch_alarm_event
    assert get_formatter({"source": "aws.alarm"}) == format_cloudwatch_alarm_event
    assert get_formatter({"source": "unknown.service"}) == format_generic_event


def test_register_custom_formatter():
    def custom_glue_formatter(event, region):
        return "Glue Custom Alert"

    register_formatter("aws.glue", custom_glue_formatter)
    assert get_formatter({"source": "aws.glue"})({"source": "aws.glue"}, "ap-southeast-1") == "Glue Custom Alert"


# --- Telegram Dispatcher & Truncation Tests ---


def test_escape_html_and_truncate():
    assert escape_html("<b>hello</b>") == "&lt;b&gt;hello&lt;/b&gt;"
    assert escape_html(None) == ""
    assert truncate_text("A" * 2000, max_len=10) == "AAAAAAAAAA... [truncated]"
    assert truncate_text(None) == ""


@patch("urllib.request.urlopen")
def test_send_telegram_message_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    res = send_telegram_message("test_token", "12345", "Hello")
    assert res["statusCode"] == 200
    assert res["response"]["ok"] is True


@patch("urllib.request.urlopen")
def test_send_telegram_message_http_error(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://api.telegram.org",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"ok":false,"description":"chat not found"}'),
    )

    with pytest.raises(RuntimeError, match="Telegram API HTTP error 400"):
        send_telegram_message("test_token", "invalid_chat", "Hello")


# --- End-to-End Handler Tests ---


@patch("packages.notifier.src.notifier.formatters.step_functions.get_stepfunctions_client")
@patch("packages.notifier.src.notifier.handler.send_telegram_message")
def test_handler_step_functions_event(mock_send, mock_get_sfn, mock_env, sample_sfn_failed_event):
    mock_sfn = MagicMock()
    mock_sfn.get_execution_history.return_value = {"events": []}
    mock_get_sfn.return_value = mock_sfn
    mock_send.return_value = {"statusCode": 200, "response": {"ok": True}}

    result = handler(sample_sfn_failed_event)
    assert result["status"] == "SUCCESS"
    assert result["source"] == "aws.states"
    assert result["statusCode"] == 200
    assert mock_send.called


@patch("packages.notifier.src.notifier.handler.send_telegram_message")
def test_handler_fallback_event(mock_send, mock_env):
    mock_send.return_value = {"statusCode": 200, "response": {"ok": True}}

    event = {
        "source": "aws.s3",
        "detail": {
            "bucket": "test-bucket",
        },
    }

    result = handler(event)
    assert result["status"] == "SUCCESS"
    assert result["source"] == "aws.s3"
    assert mock_send.called
