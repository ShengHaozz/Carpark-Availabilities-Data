output "bucket_name" {
  description = "Name of the S3 data bucket"
  value       = aws_s3_bucket.bucket.bucket
}

output "bucket_arn" {
  description = "ARN of the S3 data bucket"
  value       = aws_s3_bucket.bucket.arn
}

output "access_log_bucket_name" {
  description = "Bucket that retains S3 server access logs for 30 days"
  value       = aws_s3_bucket.access_logs.bucket
}

output "bronze_lambda_arns" {
  description = "ARNs of the Bronze ingestion Lambdas"
  value = [
    module.bronze_lambda.functions["lta_datamall"].arn,
    module.bronze_lambda.functions["hdb_data"].arn,
  ]
}
