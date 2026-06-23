# zip file for lambda
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../src/index.py"
  output_path = "lambda.zip"
}

# allow lambda to assume this role
resource "aws_iam_role" "lambda_role" {
  name = "test_lambda_role"

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
  role = aws_iam_role.lambda_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.bucket.arn,       # bucket
        "${aws_s3_bucket.bucket.arn}/*" # everything in the bucket
        # TODO: make permission narrower to just bronze layer
      ]
    }]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "test_lambda" {
  function_name = "test_lambda"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.14"
  handler       = "index.main" # main() of index.py

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.bucket.id
    }
  }
}