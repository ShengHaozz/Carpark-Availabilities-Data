variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "telegram_bot_token" {
  description = "Telegram Bot Token from @BotFather"
  type        = string
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "Telegram Chat ID or Channel ID to deliver alerts to"
  type        = string
}

variable "state_machine_arns" {
  description = "List of Step Functions state machine ARNs to monitor"
  type        = list(string)
}

variable "state_machine_statuses" {
  description = "List of Step Functions execution statuses to monitor"
  type        = list(string)
  default     = ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]
}

variable "bronze_lambda_arns" {
  description = "Bronze Lambda ARNs whose asynchronous invocation results should be sent to Telegram"
  type        = list(string)
}
