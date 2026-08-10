module "bronze_lambda" {
  source               = "./bronze_lambda"
  s3_bucket            = aws_s3_bucket.bucket
  datamall_account_key = var.datamall_account_key
}

module "silver_lambda" {
  source       = "./silver_lambda"
  s3_bucket    = aws_s3_bucket.bucket
  image_digest = var.image_digests["silver_cold"]
  repo_url     = var.ecr_repo_url
}
