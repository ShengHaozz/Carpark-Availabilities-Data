# make ecr builder role for bootstrap to assume
resource "aws_iam_role" "app_builder" {
  name = "app-builder"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [{
      Effect = "Allow"

      Principal = {
        AWS = var.bootstrap_user_arn
      }

      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "app_builder_policy" {
  name = "app-builder-policy"
  role = aws_iam_role.app_builder.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "LambdaMgmt"
        Effect = "Allow"

        Action = [
          "lambda:CreateFunction",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:PublishVersion",
          "lambda:DeleteFunction",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:ListVersionsByFunction",
          "lambda:TagResource",
          "lambda:UntagResource"
        ]

        Resource = "*"
      },

      {
        Sid    = "LambdaExecutionRoleManagement"
        Effect = "Allow"

        Action = [
          "iam:CreateRole",
          "iam:GetRole",
          "iam:DeleteRole",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:TagRole",
          "iam:UntagRole"
        ]

        Resource = "arn:aws:iam::*:role/lambda_role_*"
      },

      {
        Sid    = "PassLambdaExecutionRole"
        Effect = "Allow"

        Action = [
          "iam:PassRole"
        ]

        Resource = "arn:aws:iam::*:role/lambda-*"
      }
    ]
  })
}
