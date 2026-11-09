import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

AWS_REGION = "us-east-1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BUCKET_NAME = "pharma-devops-terraform-state-YOUR_ACCOUNT_ID"


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def run(command, check=True):
    print()
    print("=" * 70)
    print("$", " ".join(command))
    print("=" * 70)

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    if check and result.returncode != 0:
        print(f"❌ Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    return result


def get_aws_account_id():
    result = run(
        [
            "aws",
            "sts",
            "get-caller-identity",
            "--query",
            "Account",
            "--output",
            "text",
        ]
    )

    return result.stdout.strip()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    print("\n🚀 Terraform S3 Backend Bootstrap")
    print("=" * 70)

    # -----------------------------------------------------
    # 1. Check AWS credentials
    # -----------------------------------------------------

    print("\n🔍 Checking AWS credentials...")

    account_id = get_aws_account_id()

    print(f"✅ AWS Account: {account_id}")
    print(f"✅ Region: {AWS_REGION}")

    # -----------------------------------------------------
    # 2. Generate bucket name
    # -----------------------------------------------------

    bucket_name = BUCKET_NAME.replace(
        "YOUR_ACCOUNT_ID",
        account_id
    )

    print(f"\n🪣 Terraform state bucket:")
    print(f"   {bucket_name}")

    # -----------------------------------------------------
    # 3. Check whether bucket already exists
    # -----------------------------------------------------

    print("\n🔍 Checking whether S3 bucket already exists...")

    check = run(
        [
            "aws",
            "s3api",
            "head-bucket",
            "--bucket",
            bucket_name,
        ],
        check=False,
    )

    if check.returncode == 0:

        print("✅ Bucket already exists.")

    else:

        # -------------------------------------------------
        # 4. Create S3 bucket
        # -------------------------------------------------

        print("\n🪣 Creating S3 bucket...")

        run(
            [
                "aws",
                "s3api",
                "create-bucket",
                "--bucket",
                bucket_name,
                "--region",
                AWS_REGION,
            ]
        )

        print("✅ S3 bucket created.")

    # -----------------------------------------------------
    # 5. Enable versioning
    # -----------------------------------------------------

    print("\n🔐 Enabling S3 versioning...")

    run(
        [
            "aws",
            "s3api",
            "put-bucket-versioning",
            "--bucket",
            bucket_name,
            "--versioning-configuration",
            "Status=Enabled",
        ]
    )

    print("✅ Versioning enabled.")

    # -----------------------------------------------------
    # 6. Enable encryption
    # -----------------------------------------------------

    print("\n🔐 Enabling S3 encryption...")

    encryption_config = (
        '{"Rules":[{"ApplyServerSideEncryptionByDefault":'
        '{"SSEAlgorithm":"AES256"}}]}'
    )

    run(
        [
            "aws",
            "s3api",
            "put-bucket-encryption",
            "--bucket",
            bucket_name,
            "--server-side-encryption-configuration",
            encryption_config,
        ]
    )

    print("✅ AES256 encryption enabled.")

    # -----------------------------------------------------
    # 7. Block public access
    # -----------------------------------------------------

    print("\n🔒 Blocking public access...")

    run(
        [
            "aws",
            "s3api",
            "put-public-access-block",
            "--bucket",
            bucket_name,
            "--public-access-block-configuration",
            "BlockPublicAcls=true,"
            "IgnorePublicAcls=true,"
            "BlockPublicPolicy=true,"
            "RestrictPublicBuckets=true",
        ]
    )

    print("✅ Public access blocked.")

    # -----------------------------------------------------
    # 8. Add tags
    # -----------------------------------------------------

    print("\n🏷️ Adding bucket tags...")

    tagging = (
        "TagSet=["
        "{Key=Project,Value=pharma-devops-microservices},"
        "{Key=Environment,Value=shared},"
        "{Key=Purpose,Value=terraform-state},"
        "{Key=ManagedBy,Value=bootstrap-script}"
        "]"
    )

    run(
        [
            "aws",
            "s3api",
            "put-bucket-tagging",
            "--bucket",
            bucket_name,
            "--tagging",
            tagging,
        ]
    )

    print("✅ Tags added.")

    # -----------------------------------------------------
    # 9. Verify versioning
    # -----------------------------------------------------

    print("\n🔍 Verifying versioning...")

    run(
        [
            "aws",
            "s3api",
            "get-bucket-versioning",
            "--bucket",
            bucket_name,
        ]
    )

    # -----------------------------------------------------
    # 10. Verify encryption
    # -----------------------------------------------------

    print("\n🔍 Verifying encryption...")

    run(
        [
            "aws",
            "s3api",
            "get-bucket-encryption",
            "--bucket",
            bucket_name,
        ]
    )

    # -----------------------------------------------------
    # 11. Verify public access
    # -----------------------------------------------------

    print("\n🔍 Verifying public access block...")

    run(
        [
            "aws",
            "s3api",
            "get-public-access-block",
            "--bucket",
            bucket_name,
        ]
    )

    # -----------------------------------------------------
    # 12. Final result
    # -----------------------------------------------------

    print()
    print("=" * 70)
    print("✅ TERRAFORM BACKEND BOOTSTRAP COMPLETED")
    print("=" * 70)

    print("\nS3 Bucket:")
    print(f"  {bucket_name}")

    print("\nTerraform state key:")
    print("  pharma-devops/dev/terraform.tfstate")

    print("\nNext step:")
    print("  Create terraform/environments/dev/backend.tf")

    print("\nUse:")

    print(
        f'''terraform {{
  backend "s3" {{
    bucket       = "{bucket_name}"
    key          = "pharma-devops/dev/terraform.tfstate"
    region       = "{AWS_REGION}"
    encrypt      = true
    use_lockfile = true
  }}
}}'''
    )


if __name__ == "__main__":
    main()