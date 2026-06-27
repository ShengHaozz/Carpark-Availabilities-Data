# zip file for lambda
locals {
  hdb_source = "hdb"
  hdb_level  = "bronze"
}

data "archive_file" "hdb_data_zip" {
  type        = "zip"
  source_file = "${path.root}/../src/hdb_data_ingestion.py"
  output_path = "${path.module}/hdb_data.zip"
}

# allow lambda to assume this role
resource "aws_iam_role" "hdb_data_ingestion_lambda_role" {
  name = "hdb_data_ingestion_lambda_role"

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
resource "aws_iam_role_policy" "hdb_lambda_s3_put_policy" {
  name = "lambda-s3-put"
  role = aws_iam_role.hdb_data_ingestion_lambda_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject"
      ]
      Resource = [
        "${var.s3_bucket.arn}/level=${local.hdb_level}/source=${local.hdb_source}/*"
      ]
    }]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "hdb_data_lambda_logs" {
  role       = aws_iam_role.hdb_data_ingestion_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "hdb_data_ingestion" {
  function_name = "hdb_data_ingestion"
  role          = aws_iam_role.hdb_data_ingestion_lambda_role.arn
  runtime       = "python3.14"
  handler       = "hdb_data_ingestion.handler" # handler() of index.py

  filename         = data.archive_file.hdb_data_zip.output_path
  source_code_hash = data.archive_file.hdb_data_zip.output_base64sha256

  timeout = 30

  environment {
    variables = {
      BUCKET_NAME = var.s3_bucket.id
      LEVEL       = local.hdb_level
      SOURCE      = local.hdb_source
    }
  }
}
