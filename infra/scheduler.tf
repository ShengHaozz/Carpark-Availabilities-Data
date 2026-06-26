resource "aws_iam_role" "scheduler_role" {
  name = "my-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Policy to invoke lambda
resource "aws_iam_role_policy" "scheduler_lambda_policy" {
  name = "scheduler-invoke-lambda"
  role = aws_iam_role.scheduler_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.datamall_ingestion_lambda.arn
    }]
  })
}

resource "aws_scheduler_schedule" "my_schedule" {
  name = "my-lambda-schedule"

  # flexible or exact time
  flexible_time_window {
    mode = "OFF"
  }

  # cron expression for every 10 minutes
  schedule_expression = var.bronze_schedule

  target {
    arn      = aws_lambda_function.datamall_ingestion_lambda.arn
    role_arn = aws_iam_role.scheduler_role.arn
  }
}

# Resource-based permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_scheduler" {
  statement_id  = "AllowEventBridgeScheduler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.datamall_ingestion_lambda.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.my_schedule.arn
}

