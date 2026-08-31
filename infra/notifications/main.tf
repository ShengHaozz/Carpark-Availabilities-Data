data "aws_caller_identity" "current" {}

# Package Python Lambda Handler
data "archive_file" "notifier_zip" {
  type        = "zip"
  source_file = "${path.module}/../../packages/notifier/src/notifier/handler.py"
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
        "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:execution:*:*"
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

  timeout     = 30
  memory_size = 128

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.telegram_bot_token
      TELEGRAM_CHAT_ID   = var.telegram_chat_id
      AWS_REGION         = var.aws_region
    }
  }
}

# EventBridge Rule on Default Bus to capture Step Function status changes
resource "aws_cloudwatch_event_rule" "step_functions_failure_rule" {
  name        = "step-functions-telegram-alerts"
  description = "Captures Step Functions FAILED, TIMED_OUT, and ABORTED executions"

  event_pattern = var.state_machine_filter_prefix != "" ? jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status = ["FAILED", "TIMED_OUT", "ABORTED"]
      stateMachineArn = [{
        prefix = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.state_machine_filter_prefix}"
      }]
    }
    }) : jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status = ["FAILED", "TIMED_OUT", "ABORTED"]
    }
  })
}

# EventBridge Target
resource "aws_cloudwatch_event_target" "notifier_target" {
  rule      = aws_cloudwatch_event_rule.step_functions_failure_rule.name
  target_id = "step-functions-telegram-notifier"
  arn       = aws_lambda_function.telegram_notifier.arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.step_functions_failure_rule.arn
}
