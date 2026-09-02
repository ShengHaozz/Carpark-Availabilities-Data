output "lambda_function_arn" {
  description = "ARN of the Telegram Notifier Lambda"
  value       = aws_lambda_function.telegram_notifier.arn
}

output "lambda_function_name" {
  description = "Name of the Telegram Notifier Lambda"
  value       = aws_lambda_function.telegram_notifier.function_name
}

output "eventbridge_rule_arn" {
  description = "ARN of the Step Functions failure EventBridge rule"
  value       = aws_cloudwatch_event_rule.step_functions_failure_rule.arn
}
