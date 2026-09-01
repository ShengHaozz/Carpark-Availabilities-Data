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
