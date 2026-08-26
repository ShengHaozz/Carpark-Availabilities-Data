data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

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
          "s3:GetBucketLocation",
          "s3:ListBucketMultipartUploads"
        ]
        Resource = [
          var.s3_bucket.arn
        ]
      },
      {
        Sid    = "ReadSilverData"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${var.s3_bucket.arn}/level=silver/*"
        ]
      },
      {
        Sid    = "ReadWriteGoldAndAthena"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          "${var.s3_bucket.arn}/gold/*",
          "${var.s3_bucket.arn}/athena-query-results/*"
        ]
      }
    ]
  })
}

# Athena Query Execution Policy (Scoped to primary workgroup)
resource "aws_iam_role_policy" "gold_dbt_athena_policy" {
  name = "gold-dbt-athena-policy"
  role = aws_iam_role.lambda_role_gold_dbt.name

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
          "athena:ListWorkGroups",
          "athena:ListEngineVersions"
        ]
        Resource = "*"
      }
    ]
  })
}

# Glue Data Catalog Policy (Separated Read vs Write by Layer)
resource "aws_iam_role_policy" "gold_dbt_glue_policy" {
  name = "gold-dbt-glue-policy"
  role = aws_iam_role.lambda_role_gold_dbt.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueCatalogAndDatabaseRead"
        Effect = "Allow"
        Action = [
          "glue:GetDatabases",
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:BatchGetPartition"
        ]
        Resource = [
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:catalog",
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:database/silver",
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:database/prod_*",
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/silver/*",
          "arn:aws:glue:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:table/prod_*/*"
        ]
      },
      {
        Sid    = "GlueGoldTableAndDatabaseManagement"
        Effect = "Allow"
        Action = [
          "glue:CreateDatabase",
          "glue:UpdateDatabase",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
          "glue:BatchDeleteTable",
          "glue:BatchCreatePartition",
          "glue:BatchDeletePartition",
          "glue:BatchUpdatePartition"
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
