# zip file for lambda
locals {
  source = "lta"
  level  = "bronze"
}

data "archive_file" "datamall_lambda_zip" {
  type        = "zip"
  source_file = "../src/lta_datamall_ingestion.py"
  output_path = "datamall_lambda.zip"
}

# allow lambda to assume this role
resource "aws_iam_role" "datamall_ingestion_lambda_role" {
  name = "datamall_ingestion_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# attach this policy onto lambda_role
resource "aws_iam_role_policy" "lambda_s3_put_policy" {
  name = "lambda-s3-put"
  role = aws_iam_role.datamall_ingestion_lambda_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject"
      ]
      Resource = [
        "${aws_s3_bucket.bucket.arn}/level=${local.level}/source=${local.source}/*"
      ]
    }]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.datamall_ingestion_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "datamall_ingestion_lambda" {
  function_name = "datamall_ingestion_lambda"
  role          = aws_iam_role.datamall_ingestion_lambda_role.arn
  runtime       = "python3.14"
  handler       = "lta_datamall_ingestion.handler" # handler() of index.py

  filename         = data.archive_file.datamall_lambda_zip.output_path
  source_code_hash = data.archive_file.datamall_lambda_zip.output_base64sha256

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.bucket.id
      ACCOUNT_KEY = var.datamall_account_key
      LEVEL       = local.level
      SOURCE      = local.source
    }
  }
}
