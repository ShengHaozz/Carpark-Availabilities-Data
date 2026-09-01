data "aws_caller_identity" "current" {}

# Package Python Lambda Handler
data "archive_file" "notifier_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../packages/notifier/src/notifier"
  output_path = "${path.module}/lambda/notifier.zip"
}

# IAM Role for Telegram Notifier Lambda
resource "aws_iam_role" "notifier_lambda_role" {
  name = "step_functions_telegram_notifier_role"

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
  name = "step_functions_describe_execution"
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
  function_name = "step_functions_telegram_notifier"
  role          = aws_iam_role.notifier_lambda_role.arn
  runtime       = "python3.13"
  handler       = "handler.handler"

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
  target_id = "step-functions-telegram-notifier"
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
  target_id = "bronze-lambda-telegram-notifier"
  arn       = aws_lambda_function.telegram_notifier.arn
}

resource "aws_lambda_permission" "allow_bronze_eventbridge_invoke" {
  statement_id  = "AllowBronzeEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bronze_lambda_result_rule.arn
}
