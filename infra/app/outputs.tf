output "bucket_name" {
  description = "Name of the S3 data bucket"
  value       = aws_s3_bucket.bucket.bucket
}

output "bucket_arn" {
  description = "ARN of the S3 data bucket"
  value       = aws_s3_bucket.bucket.arn
}

output "bronze_lambda_arns" {
  description = "ARNs of the Bronze ingestion Lambdas"
  value = [
    module.bronze_lambda.functions["lta_datamall"].arn,
    module.bronze_lambda.functions["hdb_data"].arn,
  ]
}
