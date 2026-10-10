module "vpc" {
  source = "../../modules/vpc"

  project_name = var.project_name
  environment  = var.environment

  vpc_cidr              = "10.0.0.0/16"
  availability_zones    = ["us-east-1a", "us-east-1b"]
  public_subnet_cidrs   = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs  = ["10.0.11.0/24", "10.0.12.0/24"]
  database_subnet_cidrs = ["10.0.21.0/24", "10.0.22.0/24"]
}
module "iam" {
  source = "../../modules/iam"

  project_name = var.project_name
  environment  = var.environment
}

module "ecr" {
  source = "../../modules/ecr"

  project_name = var.project_name
  environment  = var.environment

  repository_names = [
    "frontend",
    "product-service",
    "order-service"
  ]
}

module "rds" {
  source = "../../modules/rds"

  project_name = var.project_name
  environment  = var.environment

  vpc_id              = module.vpc.vpc_id
  database_subnet_ids = module.vpc.database_subnet_ids

  allowed_cidr_blocks = [
    "10.0.11.0/24",
    "10.0.12.0/24"
  ]

  db_name           = "pharma_db"
  db_username       = "pharmaadmin"
  db_password       = var.db_password
  db_instance_class = "db.t3.micro"
}

module "eks" {
  source = "../../modules/eks"

  project_name = var.project_name
  environment  = var.environment

  cluster_name    = "pharma-dev-cluster"
  cluster_version = "1.33"

  vpc_id = module.vpc.vpc_id

  private_subnet_ids = module.vpc.private_subnet_ids

  cluster_role_arn = module.iam.eks_cluster_role_arn
  node_role_arn    = module.iam.eks_node_role_arn

  node_instance_types = ["t3.medium"]

  desired_nodes = 2
  min_nodes     = 1
  max_nodes     = 3
}

module "alb_controller" {
  source = "../../modules/alb-controller"

  project_name = var.project_name
  environment  = var.environment

  cluster_name = module.eks.cluster_name

  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
}

module "app_db_secret" {
  source = "../../modules/secrets-manager"

  project_name = var.project_name
  environment  = var.environment

  db_username = module.rds.db_username
  db_password = var.db_password
  db_host     = module.rds.db_address
  db_port     = module.rds.db_port
  db_name     = module.rds.db_name
}

module "external_secrets_iam" {
  source = "../../modules/external-secrets-iam"

  project_name = var.project_name
  environment  = var.environment

  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url

  secret_arn = module.app_db_secret.secret_arn
}
