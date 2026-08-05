module "bronze_lambda" {
  source               = "./bronze_lambda"
  s3_bucket            = aws_s3_bucket.bucket
  datamall_account_key = var.datamall_account_key
}

module "silver_lambda" {
  source       = "./silver_lambda"
  s3_bucket    = aws_s3_bucket.bucket
  image_digest = var.silver_cold_image_digest
  repo_url     = aws_ecr_lifecycle_policy.lambda_repo_policy.repository_url
}