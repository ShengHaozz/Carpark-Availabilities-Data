resource "aws_iam_role" "lambda_role_gold_dbt" {
  name = "lambda_role_gold_dbt"

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

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "gold_dbt_lambda_logs" {
  role       = aws_iam_role.lambda_role_gold_dbt.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 Policy (Read Silver, Write Gold Iceberg & Athena Query Results)
resource "aws_iam_role_policy" "gold_dbt_s3_policy" {
  name = "gold-dbt-s3-policy"
  role = aws_iam_role.lambda_role_gold_dbt.name

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
        Sid    = "ReadWriteS3Objects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.s3_bucket.arn}/*"
        ]
      }
    ]
  })
}

# Athena Query Execution Policy
resource "aws_iam_role_policy" "gold_dbt_athena_policy" {
  name = "gold-dbt-athena-policy"
  role = aws_iam_role.lambda_role_gold_dbt.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AthenaQueryExecution"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup",
          "athena:GetDataCatalog",
          "athena:GetDatabase",
          "athena:GetTableMetadata",
          "athena:ListWorkGroups",
          "athena:ListEngineVersions"
        ]
        Resource = "*"
      }
    ]
  })
}

# Glue Data Catalog Policy
resource "aws_iam_role_policy" "gold_dbt_glue_policy" {
  name = "gold-dbt-glue-policy"
  role = aws_iam_role.lambda_role_gold_dbt.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
          "glue:BatchCreatePartition",
          "glue:BatchGetPartition",
          "glue:BatchDeletePartition"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda Function
resource "aws_lambda_function" "gold_dbt_lambda" {
  function_name = "gold_dbt_lambda"
  role          = aws_iam_role.lambda_role_gold_dbt.arn
  package_type  = "Image"
  image_uri     = "${var.repo_url}@${var.image_digest}"

  architectures = ["arm64"]
  memory_size   = 1024
  timeout       = 600

  environment {
    variables = {
      ENV       = "prod"
      S3_BUCKET = var.s3_bucket.id
    }
  }
}

