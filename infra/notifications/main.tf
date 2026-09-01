# --- Default Event Bus Logging ---

resource "aws_cloudwatch_log_group" "default_bus_log" {
  name              = "/aws/events/default-log"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_resource_policy" "default_bus_log" {
  policy_name = "eventbridge-default-bus-log-policy"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = "${aws_cloudwatch_log_group.default_bus_log.arn}:*"
    }]
  })
}

resource "aws_cloudwatch_event_rule" "default_bus_log" {
  name = "eventbridge-default-log"

  event_pattern = jsonencode({
    source = [{
      prefix = ""
    }]
  })
}

resource "aws_cloudwatch_event_target" "default_bus_log" {
  rule = aws_cloudwatch_event_rule.default_bus_log.name

  target_id = "log-all-events"
  arn       = aws_cloudwatch_log_group.default_bus_log.arn
}

# Package Python Lambda Handler
data "archive_file" "notifier_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../packages/notifier/src"
  output_path = "${path.module}/lambda/notifier.zip"
}

# IAM Role for Telegram Notifier Lambda
resource "aws_iam_role" "notifier_lambda_role" {
  name = "telegram_notifier_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# IAM Policy to inspect Step Functions executions
resource "aws_iam_role_policy" "sfn_read_policy" {
  name = "telegram_notifier_step_functions_read"
  role = aws_iam_role.notifier_lambda_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "states:DescribeExecution",
        "states:GetExecutionHistory"
      ]
      Resource = [
        for arn in var.state_machine_arns :
        "${replace(arn, ":stateMachine:", ":execution:")}:*"
      ]
    }]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "notifier_lambda_logs" {
  role       = aws_iam_role.notifier_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "telegram_notifier" {
  function_name = "telegram_notifier"
  role          = aws_iam_role.notifier_lambda_role.arn
  runtime       = "python3.13"
  handler       = "notifier.handler"

  filename         = data.archive_file.notifier_zip.output_path
  source_code_hash = data.archive_file.notifier_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.telegram_bot_token
      TELEGRAM_CHAT_ID   = var.telegram_chat_id
    }
  }
}

# EventBridge Lambda Permission
resource "aws_lambda_permission" "allow_eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.step_functions_failure_rule.arn
}

# EventBridge Rule on Default Bus to capture Step Function status changes
resource "aws_cloudwatch_event_rule" "step_functions_failure_rule" {
  name        = "step-functions-telegram-alerts"
  description = "Captures Step Functions execution status changes"

  event_pattern = jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status          = var.state_machine_statuses
      stateMachineArn = var.state_machine_arns
    }
  })
}

# EventBridge Target
resource "aws_cloudwatch_event_target" "notifier_target" {
  rule      = aws_cloudwatch_event_rule.step_functions_failure_rule.name
  target_id = "telegram-notifier"
  arn       = aws_lambda_function.telegram_notifier.arn
}

# EventBridge Rule on the default bus for Bronze Lambda invocation outcomes.
resource "aws_cloudwatch_event_rule" "bronze_lambda_result_rule" {
  name        = "bronze-lambda-telegram-alerts"
  description = "Captures Bronze Lambda asynchronous invocation results"

  event_pattern = jsonencode({
    source = ["lambda"]
    detail-type = [
      "Lambda Function Invocation Result - Success",
      "Lambda Function Invocation Result - Failure",
    ]
    detail = {
      requestContext = {
        functionArn = [
          for arn in var.bronze_lambda_arns : { prefix = arn }
        ]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "bronze_lambda_notifier_target" {
  rule      = aws_cloudwatch_event_rule.bronze_lambda_result_rule.name
  target_id = "telegram-notifier"
  arn       = aws_lambda_function.telegram_notifier.arn
}

resource "aws_lambda_permission" "allow_bronze_eventbridge_invoke" {
  statement_id  = "AllowBronzeEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bronze_lambda_result_rule.arn
}
