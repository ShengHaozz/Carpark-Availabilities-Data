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
  description = "Cron Schedule for 10 mins"
  default     = "cron(0/10 * * * ? *)" # every 10 minutes
}

variable "schedule_1d" {
  type        = string
  description = "Cron Schedule for daily"
  default     = "cron(0 0 * * ? *)"
}

variable "image_digests" {
  type        = map(string)
  description = "Image digests for images in ECR"
}

variable "ecr_repo_url" {
  type        = string
  description = "URL for ECR Repository"
}

# NOTE: Update this variable with your specific Vercel production domain
# (e.g. ["https://my-carpark-app.vercel.app", "http://localhost:3000"]) when deploying frontend.
variable "cors_allowed_origins" {
  type        = list(string)
  description = "Allowed origins for Datamart CloudFront CORS (Change to your Vercel site URL for production)"
  default     = ["*"]
}

variable "datamart_version" {
  type        = string
  description = "API version route prefix for Datamart files in S3"
  default     = "v1"
}
