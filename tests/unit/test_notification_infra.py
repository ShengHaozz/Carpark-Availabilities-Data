from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_infra(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_bronze_lambdas_publish_async_results_to_default_bus():
    datamall = read_infra("infra/app/bronze_lambda/datamall_lambda.tf")
    hdb = read_infra("infra/app/bronze_lambda/hdb_lambda.tf")

    for config in (datamall, hdb):
        assert "aws_lambda_function_event_invoke_config" in config
        assert "on_success" in config
        assert "on_failure" in config
        assert "data.aws_cloudwatch_event_bus.default.arn" in config
        assert '"events:PutEvents"' in config


def test_existing_notifier_targets_bronze_lambda_result_events():
    notifier = read_infra("infra/notifications/main.tf")

    assert "aws_cloudwatch_event_rule\" \"bronze_lambda_result_rule" in notifier
    assert 'source = ["lambda"]' in notifier
    assert '"Lambda Function Invocation Result - Success"' in notifier
    assert '"Lambda Function Invocation Result - Failure"' in notifier
    assert "var.bronze_lambda_arns" in notifier


def test_default_event_bus_logs_all_events_to_cloudwatch():
    notifier = read_infra("infra/notifications/main.tf")

    assert 'name              = "/aws/events/default-log"' in notifier
    assert "retention_in_days = 7" in notifier
    assert 'resource "aws_cloudwatch_event_rule" "default_bus_log"' in notifier
    assert 'prefix = ""' in notifier
    assert 'resource "aws_cloudwatch_event_target" "default_bus_log"' in notifier
    assert "target_id = \"log-all-events\"" in notifier
    assert "arn       = aws_cloudwatch_log_group.default_bus_log.arn" in notifier


def test_notifier_is_packaged_as_a_python_module_with_general_names():
    notifier = read_infra("infra/notifications/main.tf")

    assert 'source_dir  = "${path.module}/../../packages/notifier/src"' in notifier
    assert 'function_name = "telegram_notifier"' in notifier
    assert 'name = "telegram_notifier_role"' in notifier
    assert 'handler       = "notifier.handler"' in notifier
    assert "step_functions_telegram_notifier" not in notifier
