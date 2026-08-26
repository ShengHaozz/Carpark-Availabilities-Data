# IAM Role for Step Functions State Machine Execution
resource "aws_iam_role" "step_functions_role" {
  name = "step_functions_daily_pipeline_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# IAM Policy to Invoke Silver and Gold Lambda Functions
resource "aws_iam_role_policy" "step_functions_lambda_policy" {
  name = "step-functions-lambda-invoke"
  role = aws_iam_role.step_functions_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokePipelineLambdas"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          module.silver_lambda.functions["silver_cold"].arn,
          "${module.silver_lambda.functions["silver_cold"].arn}:*",
          module.gold_lambda.functions["gold_dbt"].arn,
          "${module.gold_lambda.functions["gold_dbt"].arn}:*"
        ]
      }
    ]
  })
}

# CloudWatch Log Group for State Machine Execution Logs
resource "aws_cloudwatch_log_group" "sfn_log_group" {
  name              = "/aws/vendedlogs/states/carpark-daily-pipeline"
  retention_in_days = 14
}

# CloudWatch Logging Policy for Step Functions
resource "aws_iam_role_policy" "step_functions_logging_policy" {
  name = "step-functions-cloudwatch-logging"
  role = aws_iam_role.step_functions_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsDelivery"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# AWS Step Functions State Machine
resource "aws_sfn_state_machine" "carpark_daily_pipeline" {
  name     = "carpark-daily-pipeline"
  role_arn = aws_iam_role.step_functions_role.arn
  type     = "STANDARD"

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_log_group.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  definition = jsonencode({
    Comment = "Daily Carpark Pipeline: Transforms Bronze to Silver Cold Parquet, then executes Gold dbt models and tests."
    StartAt = "TransformSilver"
    States = {
      TransformSilver = {
        Type       = "Task"
        Resource   = "arn:aws:states:::lambda:invoke"
        OutputPath = "$.Payload"
        Parameters = {
          "FunctionName" = module.silver_lambda.functions["silver_cold"].arn
          "Payload.$"    = "$"
        }
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 10
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "PipelineFailed"
          }
        ]
        Next = "RunGoldDbt"
      }
      RunGoldDbt = {
        Type       = "Task"
        Resource   = "arn:aws:states:::lambda:invoke"
        OutputPath = "$.Payload"
        Parameters = {
          "FunctionName" = module.gold_lambda.functions["gold_dbt"].arn
          "Payload.$"    = "$"
        }
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 15
            MaxAttempts     = 2
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "PipelineFailed"
          }
        ]
        Next = "PipelineSucceeded"
      }
      PipelineSucceeded = {
        Type = "Succeed"
      }
      PipelineFailed = {
        Type  = "Fail"
        Cause = "Daily carpark pipeline step failed."
        Error = "PipelineExecutionError"
      }
    }
  })
}

output "step_function_arn" {
  value       = aws_sfn_state_machine.carpark_daily_pipeline.arn
  description = "ARN of the Step Functions Daily Pipeline State Machine"
}

