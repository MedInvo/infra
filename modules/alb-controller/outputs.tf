output "role_arn" {
  value = aws_iam_role.alb_controller.arn
}

output "role_name" {
  value = aws_iam_role.alb_controller.name
}