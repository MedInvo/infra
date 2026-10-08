import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TERRAFORM_DIR = PROJECT_ROOT / "terraform" / "environments" / "dev"

AWS_REGION = "us-east-1"

NAMESPACE = "external-secrets"

SERVICE_ACCOUNT = "external-secrets"

HELM_REPO_NAME = "external-secrets"

HELM_REPO_URL = "https://charts.external-secrets.io"

CHART_NAME = "external-secrets/external-secrets"


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def run(command):
    print()
    print("=" * 70)
    print("$", " ".join(str(item) for item in command))
    print("=" * 70)

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
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
# Check required commands
# ---------------------------------------------------------

print("\n🔍 Checking required commands...")

required_commands = [
    "aws",
    "kubectl",
    "helm",
    "terraform",
]

for command in required_commands:

    result = subprocess.run(
        ["which", command],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print(f"❌ Required command not found: {command}")
        sys.exit(1)

    print(f"✅ {command}")


# ---------------------------------------------------------
# Get EKS cluster name
# ---------------------------------------------------------

print("\n🔍 Getting EKS cluster name...")

result = run(
    [
        "terraform",
        f"-chdir={TERRAFORM_DIR}",
        "output",
        "-raw",
        "eks_cluster_name",
    ]
)

cluster_name = result.stdout.strip()

if not cluster_name:
    print("❌ EKS cluster name was not returned.")
    sys.exit(1)

print(f"✅ Cluster: {cluster_name}")


# ---------------------------------------------------------
# Get ESO IAM Role ARN
# ---------------------------------------------------------

print("\n🔍 Getting External Secrets IAM role ARN...")

result = run(
    [
        "terraform",
        f"-chdir={TERRAFORM_DIR}",
        "output",
        "-raw",
        "external_secrets_role_arn",
    ]
)

role_arn = result.stdout.strip()

if not role_arn:
    print("❌ External Secrets IAM role ARN was not returned.")
    print()
    print("Make sure Terraform creates:")
    print("  external_secrets_role_arn")
    sys.exit(1)

print(f"✅ ESO IAM Role: {role_arn}")


# ---------------------------------------------------------
# Verify Kubernetes connection
# ---------------------------------------------------------

print("\n🔍 Checking Kubernetes connection...")

run(
    [
        "kubectl",
        "cluster-info",
    ]
)


# ---------------------------------------------------------
# Add External Secrets Helm repository
# ---------------------------------------------------------

print("\n📦 Adding External Secrets Helm repository...")

run(
    [
        "helm",
        "repo",
        "add",
        HELM_REPO_NAME,
        HELM_REPO_URL,
    ]
)


# ---------------------------------------------------------
# Update Helm repositories
# ---------------------------------------------------------

print("\n🔄 Updating Helm repositories...")

run(
    [
        "helm",
        "repo",
        "update",
    ]
)


# ---------------------------------------------------------
# Create namespace
# ---------------------------------------------------------

print("\n📦 Creating External Secrets namespace...")

run(
    [
        "kubectl",
        "create",
        "namespace",
        NAMESPACE,
        "--dry-run=client",
        "-o",
        "yaml",
    ]
)

namespace_yaml = subprocess.run(
    [
        "kubectl",
        "create",
        "namespace",
        NAMESPACE,
        "--dry-run=client",
        "-o",
        "yaml",
    ],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
)

if namespace_yaml.returncode != 0:
    print(namespace_yaml.stderr, file=sys.stderr)
    sys.exit(1)

apply_result = subprocess.run(
    [
        "kubectl",
        "apply",
        "-f",
        "-",
    ],
    cwd=PROJECT_ROOT,
    input=namespace_yaml.stdout,
    text=True,
    capture_output=True,
)

if apply_result.stdout:
    print(apply_result.stdout, end="")

if apply_result.stderr:
    print(apply_result.stderr, end="", file=sys.stderr)

if apply_result.returncode != 0:
    print("❌ Failed to create namespace.")
    sys.exit(1)


# ---------------------------------------------------------
# Install / upgrade External Secrets Operator
# ---------------------------------------------------------

print("\n🚀 Installing External Secrets Operator...")

run(
    [
        "helm",
        "upgrade",
        "--install",
        "external-secrets",
        CHART_NAME,
        "--namespace",
        NAMESPACE,
        "--create-namespace",
        "--set",
        "installCRDs=true",
        "--set",
        "serviceAccount.create=true",
        "--set",
        f"serviceAccount.name={SERVICE_ACCOUNT}",
        "--set",
        f"serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn={role_arn}",
    ]
)


# ---------------------------------------------------------
# Wait for External Secrets Operator
# ---------------------------------------------------------

print("\n⏳ Waiting for External Secrets Operator...")

run(
    [
        "kubectl",
        "rollout",
        "status",
        "deployment/external-secrets",
        "--namespace",
        NAMESPACE,
        "--timeout=180s",
    ]
)


# ---------------------------------------------------------
# Verify ESO deployment
# ---------------------------------------------------------

print("\n🔍 Checking External Secrets deployments...")

run(
    [
        "kubectl",
        "get",
        "deployments",
        "--namespace",
        NAMESPACE,
    ]
)


# ---------------------------------------------------------
# Verify ESO pods
# ---------------------------------------------------------

print("\n🔍 Checking External Secrets pods...")

run(
    [
        "kubectl",
        "get",
        "pods",
        "--namespace",
        NAMESPACE,
        "-o",
        "wide",
    ]
)


# ---------------------------------------------------------
# Verify CRDs
# ---------------------------------------------------------

print("\n🔍 Checking External Secrets CRDs...")

run(
    [
        "kubectl",
        "get",
        "crd",
        "externalsecrets.external-secrets.io",
        "secretstores.external-secrets.io",
        "clustersecretstores.external-secrets.io",
    ]
)


# ---------------------------------------------------------
# Final message
# ---------------------------------------------------------

print()
print("=" * 70)
print("✅ EXTERNAL SECRETS OPERATOR INSTALLED")
print("=" * 70)

print()
print("Cluster:")
print(f"  {cluster_name}")

print()
print("Namespace:")
print(f"  {NAMESPACE}")

print()
print("ServiceAccount:")
print(f"  {SERVICE_ACCOUNT}")

print()
print("Next step:")
print("  python3 scripts/phase6_08_verify_infrastructure.py")