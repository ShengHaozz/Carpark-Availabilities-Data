# make ecr builder role for bootstrap to assume
resource "aws_iam_role" "ecr_builder" {
  name = "ecr-builder"

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

resource "aws_iam_role_policy" "ecr_builder_policy" {
  name = "ecr-builder-policy"
  role = aws_iam_role.ecr_builder.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ECRAuthorizationForDocker"
        Effect = "Allow"

        Action = [
          "ecr:GetAuthorizationToken"
        ]

        Resource = "*"
      },

      {
        Sid    = "ECRRepoManagement"
        Effect = "Allow"

        Action = [
          "ecr:CreateRepository",
          "ecr:DescribeRepositories",
          "ecr:DescribeImages",
          "ecr:DeleteRepository",
          "ecr:PutLifecyclePolicy",
          "ecr:GetLifecyclePolicy",
          "ecr:DeleteLifecyclePolicy"
        ]

        Resource = "*"
      },

      {
        Sid    = "ECRImagePushPull"
        Effect = "Allow"

        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:CompleteLayerUpload",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart"
        ]

        Resource = "*"
      }
    ]
  })
}
