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

# S3 Policy: Read Athena query results & Put datamart JSON documents
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
        Sid    = "ReadAthenaQueryResults"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${var.s3_bucket.arn}/athena-query-results/*"
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
          "${var.s3_bucket.arn}/level=datamart/*",
          "${var.s3_bucket.arn}/athena-query-results/*"
        ]
      }
    ]
  })
}

# Athena Query Execution Policy (Scoped to primary workgroup)
resource "aws_iam_role_policy" "datamart_athena_policy" {
  name = "datamart-publisher-athena-policy"
  role = aws_iam_role.lambda_role_datamart_publisher.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AthenaWorkgroupExecution"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup"
        ]
        Resource = [
          "arn:aws:athena:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:workgroup/primary"
        ]
      },
      {
        Sid    = "AthenaGlobalDiscovery"
        Effect = "Allow"
        Action = [
          "athena:GetDataCatalog",
          "athena:GetDatabase",
          "athena:GetTableMetadata",
          "athena:ListWorkGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# Glue Data Catalog Read-Only Policy for Gold Marts
resource "aws_iam_role_policy" "datamart_glue_policy" {
  name = "datamart-publisher-glue-policy"
  role = aws_iam_role.lambda_role_datamart_publisher.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueCatalogAndMartsRead"
        Effect = "Allow"
        Action = [
          "glue:GetDatabases",
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetTableVersion",
          "glue:GetTableVersions",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:BatchGetPartition"
        ]
        Resource = [
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:catalog",
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:database/prod_*",
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/prod_*/*"
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
      DATABASE         = "prod_marts"
      TABLE_NAME       = "mart_carpark_day_of_week_distribution"
      DATAMART_VERSION = "v1"
    }
  }
}
