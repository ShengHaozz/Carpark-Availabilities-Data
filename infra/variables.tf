variable "aws_region" {
  default = "ap-southeast-1"
}

variable "bucket_name" {
  default = "shenghao-carpark-availability-bucket"
}

variable "access_key" {
  type        = string
  description = "Access Key for Terraform IAM user"
}

variable "secret_key" {
  type        = string
  description = "Secret Key for Terraform IAM User"
}

variable "datamall_account_key" {
  type        = string
  description = "Account Key for LTA DataMall"
}

variable "bronze_schedule" {
  type        = string
  description = "Cron Schedule for bronze ingestion lambda functions"
  default     = "cron(0/10 * * * ? *)" # every 10 minutes
}
