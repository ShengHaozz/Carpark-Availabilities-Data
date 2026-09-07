data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Archive python package source for lightweight deployment (Zero heavy container needed)
data "archive_file" "datamart_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../../packages/datamart/src"
  output_path = "${path.module}/lambda/datamart.zip"
}

# IAM Role for Datamart Publisher Lambda
resource "aws_iam_role" "lambda_role_datamart_publisher" {
  name = "lambda_role_datamart_publisher"

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

# CloudWatch Logs Basic Execution
resource "aws_iam_role_policy_attachment" "datamart_publisher_lambda_logs" {
  role       = aws_iam_role.lambda_role_datamart_publisher.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 Policy: Read CSV Marts & Put downstream JSON documents
resource "aws_iam_role_policy" "datamart_s3_policy" {
  name = "datamart-publisher-s3-policy"
  role = aws_iam_role.lambda_role_datamart_publisher.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          var.s3_bucket.arn
        ]
      },
      {
        Sid    = "ReadMartCsv"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${var.s3_bucket.arn}/level=mart/target=publisher/*"
        ]
      },
      {
        Sid    = "WriteDatamartDocuments"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          "${var.s3_bucket.arn}/level=mart/target=downstream/*"
        ]
      }
    ]
  })
}

# Dedicated Datamart Lambda Function (Zip-based, lightweight, arm64)
resource "aws_lambda_function" "datamart_publisher_lambda" {
  function_name = "datamart_publisher_lambda"
  role          = aws_iam_role.lambda_role_datamart_publisher.arn
  runtime       = "python3.12"
  handler       = "datamart.handler.handler"

  filename         = data.archive_file.datamart_zip.output_path
  source_code_hash = data.archive_file.datamart_zip.output_base64sha256

  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 300

  environment {
    variables = {
      ENV              = "prod"
      S3_BUCKET        = var.s3_bucket.id
      INPUT_PREFIX     = "level=mart/target=publisher/mart_carpark_day_of_week_distribution"
      OUTPUT_PREFIX    = "level=mart/target=downstream"
      DATAMART_VERSION = "v1"
    }
  }
}
