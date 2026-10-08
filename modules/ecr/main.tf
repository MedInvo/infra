resource "aws_ecr_repository" "this" {
  for_each = var.repository_names

  name                 = "${var.project_name}-${var.environment}-${each.value}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}
