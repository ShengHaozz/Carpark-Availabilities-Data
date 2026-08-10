locals {
  scheduler_10m_name = "scheduler_10m"
}

resource "aws_cloudwatch_event_bus" "main" {
  name = "carpark-events"
}

resource "aws_iam_role" "scheduler_role" {
  name = "carpark-scheduler-role"

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
resource "aws_iam_role_policy" "scheduler_policy" {
  name = "carpark-scheduler-policy"
  role = aws_iam_role.scheduler_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:PutEvents"
      Resource = aws_cloudwatch_event_bus.main.arn
    }]
  })
}

resource "aws_scheduler_schedule" "scheduler_10m" {
  name = local.scheduler_10m_name

  # flexible or exact time
  flexible_time_window {
    mode = "OFF"
  }

  # cron expression for every 10 minutes
  schedule_expression = var.schedule_10m

  target {
    arn      = aws_cloudwatch_event_bus.main.arn
    role_arn = aws_iam_role.scheduler_role.arn

    input = jsonencode({
      source   = local.scheduler_10m_name
      interval = "10m"
    })
  }
}

resource "aws_cloudwatch_event_rule" "scheduler_10m" {
  name           = "scheduler-10m-rule"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = [
      aws_scheduler_schedule.scheduler_10m.name
    ]
  })
}

resource "aws_cloudwatch_event_target" "lta-datamall" {
  rule           = aws_cloudwatch_event_rule.scheduler_10m.name
  event_bus_name = aws_cloudwatch_event_bus.main.name

  target_id = "lta-datamall"
  arn       = module.bronze_lambda.functions["lta_datamall"].arn
}

resource "aws_cloudwatch_event_target" "hdb-data" {
  rule           = aws_cloudwatch_event_rule.scheduler_10m.name
  event_bus_name = aws_cloudwatch_event_bus.main.name

  target_id = "hdb-data"
  arn       = module.bronze_lambda.functions["hdb_data"].arn
}


