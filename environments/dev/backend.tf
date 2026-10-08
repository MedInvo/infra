terraform {
  backend "s3" {
    bucket       = "pharma-medinvo-terraform-state-upendra-2026"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}