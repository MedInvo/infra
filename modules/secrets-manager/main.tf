resource "aws_secretsmanager_secret" "app_db" {
  name                    = "${var.project_name}/${var.environment}/app-db"
  description             = "Application PostgreSQL credentials"
  recovery_window_in_days = 30

  # Prevent accidental deletion through Terraform.
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "app_db" {
  secret_id = aws_secretsmanager_secret.app_db.id

  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = var.db_host
    port     = var.db_port
    dbname   = var.db_name
  })
}
