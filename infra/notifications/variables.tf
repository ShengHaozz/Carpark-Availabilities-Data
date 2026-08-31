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

variable "state_machine_filter_prefix" {
  description = "Prefix of Step Functions state machines to monitor (e.g. 'carpark-'). Leave empty to monitor all."
  type        = string
  default     = "carpark-"
}
