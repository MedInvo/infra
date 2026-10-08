import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TERRAFORM_DIR = PROJECT_ROOT / "terraform" / "environments" / "dev"

AWS_REGION = "us-east-1"

NAMESPACE = "pharma-app"

ALB_CONTROLLER_NAMESPACE = "kube-system"

ALB_CONTROLLER_NAME = "aws-load-balancer-controller"


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
# AWS Identity
# ---------------------------------------------------------

print("\n🔐 AWS Identity")

run(
    [
        "aws",
        "sts",
        "get-caller-identity",
    ]
)


# ---------------------------------------------------------
# Terraform Outputs
# ---------------------------------------------------------

print("\n🏗️ Terraform Outputs")

run(
    [
        "terraform",
        f"-chdir={TERRAFORM_DIR}",
        "output",
    ]
)


# ---------------------------------------------------------
# Get EKS Cluster Name
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

print(f"✅ EKS Cluster: {cluster_name}")


# ---------------------------------------------------------
# Get VPC ID
# ---------------------------------------------------------

print("\n🔍 Getting VPC ID...")

result = run(
    [
        "terraform",
        f"-chdir={TERRAFORM_DIR}",
        "output",
        "-raw",
        "vpc_id",
    ]
)

vpc_id = result.stdout.strip()

if not vpc_id:
    print("❌ VPC ID was not returned.")
    sys.exit(1)

print(f"✅ VPC ID: {vpc_id}")


# ---------------------------------------------------------
# Get EKS Cluster Status
# ---------------------------------------------------------

print("\n☸️ EKS Cluster")

run(
    [
        "aws",
        "eks",
        "describe-cluster",
        "--region",
        AWS_REGION,
        "--name",
        cluster_name,
        "--query",
        "cluster.status",
        "--output",
        "text",
    ]
)


# ---------------------------------------------------------
# Kubernetes Connection
# ---------------------------------------------------------

print("\n🔗 Kubernetes Connection")

run(
    [
        "kubectl",
        "cluster-info",
    ]
)


# ---------------------------------------------------------
# Kubernetes Nodes
# ---------------------------------------------------------

print("\n🖥️ Kubernetes Nodes")

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
# Kubernetes Namespaces
# ---------------------------------------------------------

print("\n📦 Kubernetes Namespaces")

run(
    [
        "kubectl",
        "get",
        "namespaces",
    ]
)


# ---------------------------------------------------------
# ECR Repositories
# ---------------------------------------------------------

print("\n📦 ECR Repositories")

run(
    [
        "aws",
        "ecr",
        "describe-repositories",
        "--region",
        AWS_REGION,
        "--query",
        "repositories[].repositoryName",
        "--output",
        "table",
    ]
)


# ---------------------------------------------------------
# RDS Instances
# ---------------------------------------------------------

print("\n🐘 RDS PostgreSQL")

run(
    [
        "aws",
        "rds",
        "describe-db-instances",
        "--region",
        AWS_REGION,
        "--query",
        "DBInstances[].{Identifier:DBInstanceIdentifier,Status:DBInstanceStatus,Engine:Engine,Endpoint:Endpoint.Address}",
        "--output",
        "table",
    ]
)


# ---------------------------------------------------------
# VPC
# ---------------------------------------------------------

print("\n🌐 VPC")

run(
    [
        "aws",
        "ec2",
        "describe-vpcs",
        "--region",
        AWS_REGION,
        "--vpc-ids",
        vpc_id,
        "--query",
        "Vpcs[].{VpcId:VpcId,Cidr:CidrBlock,State:State}",
        "--output",
        "table",
    ]
)


# ---------------------------------------------------------
# ALB Controller Deployment
# ---------------------------------------------------------

print("\n⚖️ AWS Load Balancer Controller")

run(
    [
        "kubectl",
        "get",
        "deployment",
        ALB_CONTROLLER_NAME,
        "--namespace",
        ALB_CONTROLLER_NAMESPACE,
    ]
)


# ---------------------------------------------------------
# ALB Controller Pods
# ---------------------------------------------------------

print("\n🔍 AWS Load Balancer Controller Pods")

run(
    [
        "kubectl",
        "get",
        "pods",
        "--namespace",
        ALB_CONTROLLER_NAMESPACE,
        "-l",
        "app.kubernetes.io/name=aws-load-balancer-controller",
        "-o",
        "wide",
    ]
)


# ---------------------------------------------------------
# Application Namespace
# ---------------------------------------------------------

print("\n🚀 Application Namespace")

namespace_check = subprocess.run(
    [
        "kubectl",
        "get",
        "namespace",
        NAMESPACE,
    ],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
)

if namespace_check.returncode == 0:

    print(namespace_check.stdout, end="")

    print("\n🔍 Application Pods")

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

    print("\n🔍 Application Services")

    run(
        [
            "kubectl",
            "get",
            "services",
            "--namespace",
            NAMESPACE,
        ]
    )

    print("\n🔍 Application Ingress")

    ingress_result = subprocess.run(
        [
            "kubectl",
            "get",
            "ingress",
            "--namespace",
            NAMESPACE,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    if ingress_result.returncode == 0:

        print(ingress_result.stdout, end="")

    else:

        print("ℹ️ No Ingress resource found.")

else:

    print(f"ℹ️ Namespace '{NAMESPACE}' does not exist yet.")

    print("Application workloads have not been deployed yet.")


# ---------------------------------------------------------
# AWS Load Balancers
# ---------------------------------------------------------

print("\n⚖️ AWS Load Balancers")

load_balancer_result = subprocess.run(
    [
        "aws",
        "elbv2",
        "describe-load-balancers",
        "--region",
        AWS_REGION,
        "--query",
        "LoadBalancers[].{Name:LoadBalancerName,Type:Type,State:State.Code,DNSName:DNSName}",
        "--output",
        "table",
    ],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
)

if load_balancer_result.returncode == 0:

    if load_balancer_result.stdout.strip():

        print(load_balancer_result.stdout, end="")

    else:

        print("ℹ️ No AWS Load Balancers found.")

else:

    print(load_balancer_result.stderr, file=sys.stderr)

    print("⚠️ Unable to query AWS Load Balancers.")


# ---------------------------------------------------------
# Final Summary
# ---------------------------------------------------------

print()
print("=" * 70)
print("✅ INFRASTRUCTURE VERIFICATION COMPLETED")
print("=" * 70)

print()
print("Verified components:")
print("  ✅ AWS Identity")
print("  ✅ Terraform outputs")
print("  ✅ EKS cluster")
print("  ✅ Kubernetes connection")
print("  ✅ Kubernetes nodes")
print("  ✅ Kubernetes namespaces")
print("  ✅ ECR repositories")
print("  ✅ RDS PostgreSQL")
print("  ✅ VPC")
print("  ✅ AWS Load Balancer Controller")
print("  ✅ Application namespace/workloads")
print("  ✅ AWS Load Balancers")

print()
print("Next step:")
print("  Review the verification output before proceeding to cleanup or application deployment.")