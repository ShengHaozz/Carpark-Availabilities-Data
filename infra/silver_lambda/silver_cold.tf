# allow lambda to assume this role
locals {
  input_level  = "bronze"
  lta_source   = "lta"
  hdb_source   = "hdb"
  output_level = "silver"
}

resource "aws_iam_role" "silver_cold_lambda_role" {
  name = "silver_cold_lambda_role"

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
resource "aws_iam_role_policy" "silver_cold_s3_policy" {
  name = "lambda-s3-put"
  role = aws_iam_role.silver_cold_lambda_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadFromBronze"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${var.s3_bucket.arn}/level=bronze/*"
        ]
      },
      {
        Sid    = "WriteToSilver"
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = [
          "${var.s3_bucket.arn}/level=silver/*"
        ]
      }
    ]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "silver_cold_lambda_logs" {
  role       = aws_iam_role.silver_cold_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "silver_cold_lambda" {
  function_name = "silver_cold_lambda"
  role          = aws_iam_role.silver_cold_lambda_role.arn
  package_type  = "Image"
  image_uri     = "${var.repo_url}@${var.image_digest}"

  architectures = ["arm64"]
  memory_size   = 512
  timeout       = 30

  environment {
    variables = {
      BUCKET_NAME  = var.s3_bucket.id
      INPUT_LEVEL  = local.input_level
      LTA_SOURCE   = local.lta_source
      HDB_SOURCE   = local.hdb_source
      OUTPUT_LEVEL = local.output_level
    }
  }
}
