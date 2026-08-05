resource "aws_ecr_repository" "lambda_repo" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration { # scan for CVE
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "lambda_repo_policy" {
  repository = aws_ecr_repository.lambda_repo.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 30 days" # new image causes old images to be untagged and cleaned up
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
