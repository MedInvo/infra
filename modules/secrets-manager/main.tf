
resource "aws_secretsmanager_secret" "app_db" {
  name        = "${var.project_name}/${var.environment}/app-db"
  description = "Application PostgreSQL credentials"
  # This is a disposable demo environment. Force deletion lets a subsequent
  # Terraform apply recreate the same secret name without a recovery-window
  # conflict.
  recovery_window_in_days = 0

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "app_db" {

  count     = var.manage_secret_version ? 1 : 0
  secret_id = aws_secretsmanager_secret.app_db.id

  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = var.db_host
    port     = var.db_port
    dbname   = var.db_name
  })
}
