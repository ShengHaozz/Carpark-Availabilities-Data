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
      Effect = "Allow"
      Action = "lambda:InvokeFunction"
      Resource = [
        module.lambda.functions.lta_datamall.arn,
        module.lambda.functions.hdb_data.arn
      ]

    }]
  })
}

resource "aws_scheduler_schedule" "bronze_schedule" {
  for_each = module.lambda.functions
  name     = "${each.key}_bronze_schedule"

  # flexible or exact time
  flexible_time_window {
    mode = "OFF"
  }

  # cron expression for every 10 minutes
  schedule_expression = var.bronze_schedule

  target {
    arn      = each.value.arn
    role_arn = aws_iam_role.scheduler_role.arn
  }
}

# Resource-based permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_scheduler" {
  for_each = module.lambda.functions

  statement_id  = "AllowEventBridgeScheduler"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.bronze_schedule[each.key].arn
}

