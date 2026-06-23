variable "aws_region" {
  default = "ap-southeast-1"
}

variable "bucket_name" {
  default = "shenghao-car-availability-bucket"
}

variable "access_key" {
  type        = string
  description = "Access Key for Terraform IAM user"
}

variable "secret_key" {
  type        = string
  description = "Secret Key for Terraform IAM User"
}