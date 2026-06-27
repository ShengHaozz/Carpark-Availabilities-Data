module "lambda" {
  source               = "./lambda"
  s3_bucket            = aws_s3_bucket.bucket
  datamall_account_key = var.datamall_account_key
}
