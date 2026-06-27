# zip file for lambda
locals {
  lta_source = "lta"
  lta_level  = "bronze"
}

data "archive_file" "datamall_lambda_zip" {
  type        = "zip"
  source_file = "${path.root}/../src/lta_datamall_ingestion.py"
  output_path = "${path.module}/datamall_lambda.zip"
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
resource "aws_iam_role_policy" "lta_lambda_s3_put_policy" {
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
        "${var.s3_bucket.arn}/level=${local.lta_level}/source=${local.lta_source}/*"
      ]
    }]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "lta_datamall_lambda_logs" {
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

  timeout = 30

  environment {
    variables = {
      BUCKET_NAME = var.s3_bucket.id
      ACCOUNT_KEY = var.datamall_account_key
      LEVEL       = local.lta_level
      SOURCE      = local.lta_source
    }
  }
}
