variable "aws_region" {
  default = "ap-southeast-1"
}

variable "bucket_name" {
  default = "shenghao-carpark-availability-bucket"
}

variable "datamall_account_key" {
  type        = string
  description = "Account Key for LTA DataMall"
}

variable "schedule_10m" {
  type        = string
  description = "Cron Schedule for bronze ingestion lambda functions"
  default     = "cron(0/10 * * * ? *)" # every 10 minutes
}

variable "image_digests" {
  type        = map(string)
  description = "Image digests for images in ECR"
}

variable "ecr_repo_url" {
  type        = string
  description = "URL for ECR Repository"
}
