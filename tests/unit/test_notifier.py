import json
import urllib.error
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from packages.notifier.src.notifier.handler import (
    build_console_url,
    build_telegram_message,
    extract_failure_details_from_history,
    format_duration,
    format_timestamp,
    handler,
    send_telegram_message,
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


def test_build_telegram_message_html_escaping():
    msg = build_telegram_message(
        state_machine_name="carpark<test>&pipeline",
        status="FAILED",
        execution_name="exec<1>",
        execution_arn="arn:aws:states:exec",
        region="ap-southeast-1",
        duration_str="2m",
        timestamp_str="2026-08-31 01:00:00 UTC",
        failed_state="Transform<Silver>",
        error_code="Error&Fail",
        error_cause="<script>alert('xss')</script>",
    )
    assert "&lt;test&gt;" in msg
    assert "&amp;pipeline" in msg
    assert "&lt;script&gt;" in msg
    assert "<script>" not in msg


def test_build_telegram_message_truncation():
    very_long_cause = "E" * 5000
    msg = build_telegram_message(
        state_machine_name="carpark-pipeline",
        status="FAILED",
        execution_name="exec-1",
        execution_arn="arn:aws:states:exec",
        region="ap-southeast-1",
        duration_str="1m",
        timestamp_str="2026-08-31",
        error_cause=very_long_cause,
    )
    assert len(msg) <= 4000
    assert "[truncated]" in msg


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


@patch("packages.notifier.src.notifier.handler.get_stepfunctions_client")
@patch("packages.notifier.src.notifier.handler.send_telegram_message")
def test_handler_end_to_end(mock_send, mock_get_sfn, mock_env, sample_sfn_failed_event):
    mock_sfn = MagicMock()
    mock_sfn.get_execution_history.return_value = {
        "events": [
            {
                "type": "TaskStateEntered",
                "stateEnteredEventDetails": {"name": "RunGoldDbt"},
            },
            {
                "type": "TaskFailed",
                "taskFailedEventDetails": {
                    "error": "DbtBuildError",
                    "cause": "Model fct_lot_availability failed",
                },
            },
        ]
    }
    mock_get_sfn.return_value = mock_sfn
    mock_send.return_value = {"statusCode": 200, "response": {"ok": True}}

    result = handler(sample_sfn_failed_event)
    assert result["status"] == "SUCCESS"
    assert result["state_machine"] == "carpark-daily-pipeline"
    assert result["statusCode"] == 200
    assert mock_send.called
