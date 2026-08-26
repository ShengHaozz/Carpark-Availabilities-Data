variable "image_digest" {
  type        = string
  description = "Image digest for the gold dbt lambda function"
}

variable "repo_url" {
  type        = string
  description = "ECR repository URL for the gold dbt lambda function"
}

variable "s3_bucket" {
  type        = any
  description = "S3 bucket for the lambda function"
}

