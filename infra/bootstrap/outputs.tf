output "ecr_builder_role_arn" {
  value = aws_iam_role.ecr_builder
}

output "app_builder_role_arn" {
  value = aws_iam_role.app_builder
}
