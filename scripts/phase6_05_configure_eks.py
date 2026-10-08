import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = PROJECT_ROOT / "terraform" / "environments" / "dev"

AWS_REGION = "us-east-1"


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def run(command):
    print()
    print("=" * 70)
    print("$", " ".join(command))
    print("=" * 70)

    result = subprocess.run(
        command,
        cwd=TERRAFORM_DIR,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        print()
        print("❌ Command failed.")
        sys.exit(result.returncode)

    print("✅ Command completed successfully.")
    return result


# ---------------------------------------------------------
# Get EKS cluster name from Terraform
# ---------------------------------------------------------

print("\n🔍 Getting EKS cluster name from Terraform...")

result = run(
    [
        "terraform",
        "output",
        "-raw",
        "eks_cluster_name",
    ]
)

cluster_name = result.stdout.strip()

if not cluster_name:
    print("❌ EKS cluster name was not returned by Terraform.")
    sys.exit(1)

print(f"✅ EKS cluster: {cluster_name}")


# ---------------------------------------------------------
# Update kubeconfig
# ---------------------------------------------------------

print("\n🔧 Updating kubeconfig...")

run(
    [
        "aws",
        "eks",
        "update-kubeconfig",
        "--region",
        AWS_REGION,
        "--name",
        cluster_name,
    ]
)


# ---------------------------------------------------------
# Check kubectl context
# ---------------------------------------------------------

print("\n🔍 Checking current kubectl context...")

run(
    [
        "kubectl",
        "config",
        "current-context",
    ]
)


# ---------------------------------------------------------
# Check nodes
# ---------------------------------------------------------

print("\n🔍 Checking EKS nodes...")

run(
    [
        "kubectl",
        "get",
        "nodes",
        "-o",
        "wide",
    ]
)


# ---------------------------------------------------------
# Check namespaces
# ---------------------------------------------------------

print("\n🔍 Checking Kubernetes namespaces...")

run(
    [
        "kubectl",
        "get",
        "namespaces",
    ]
)


print()
print("=" * 70)
print("✅ EKS CONFIGURATION COMPLETED")
print("=" * 70)

print()
print("Your kubectl is now connected to:")
print(f"  {cluster_name}")

print()
print("Next step:")
print("  python3 scripts/phase6_06_install_alb_controller.py")