import subprocess
import sys
import time


# =========================================================
# Configuration
# =========================================================

AWS_REGION = "us-east-1"

APPLICATION_NAMESPACE = "pharma-app"

ALB_CONTROLLER_NAMESPACE = "kube-system"

ALB_CONTROLLER_RELEASE = "aws-load-balancer-controller"

MAX_WAIT_SECONDS = 300

CHECK_INTERVAL_SECONDS = 10


# =========================================================
# Helper
# =========================================================

def run(command, allow_failure=False):
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

    if result.returncode != 0:

        if allow_failure:
            print("⚠️ Command failed, continuing...")
            return result

        print("❌ Command failed.")
        sys.exit(result.returncode)

    return result


# =========================================================
# Check required commands
# =========================================================

print()
print("=" * 70)
print("PHASE 6.08 - CLEANUP EXTERNAL RESOURCES")
print("=" * 70)

print("\n🔍 Checking required commands...")

for command in ["kubectl", "helm", "aws"]:

    result = subprocess.run(
        ["which", command],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print(f"❌ Required command not found: {command}")
        sys.exit(1)

    print(f"✅ {command}")


# =========================================================
# Check Kubernetes connection
# =========================================================

print("\n☸️ Checking Kubernetes connection...")

cluster_check = run(
    [
        "kubectl",
        "cluster-info",
    ],
    allow_failure=True,
)

if cluster_check.returncode != 0:
    print()
    print("❌ Kubernetes cluster is not reachable.")
    print()
    print("This script must run while the EKS cluster still exists.")
    sys.exit(1)


# =========================================================
# Show current Ingress resources
# =========================================================

print("\n🌍 Current application Ingress resources...")

run(
    [
        "kubectl",
        "get",
        "ingress",
        "--namespace",
        APPLICATION_NAMESPACE,
    ],
    allow_failure=True,
)


# =========================================================
# Delete application Ingress
# =========================================================

print("\n🗑️ Deleting application Ingress resources...")

run(
    [
        "kubectl",
        "delete",
        "ingress",
        "--all",
        "--namespace",
        APPLICATION_NAMESPACE,
        "--ignore-not-found=true",
        "--wait=true",
    ],
)


# =========================================================
# Wait for ALB deletion
# =========================================================

print()
print("=" * 70)
print("⏳ WAITING FOR AWS LOAD BALANCER CLEANUP")
print("=" * 70)

elapsed = 0
alb_deleted = False

while elapsed < MAX_WAIT_SECONDS:

    result = subprocess.run(
        [
            "aws",
            "elbv2",
            "describe-load-balancers",
            "--region",
            AWS_REGION,
            "--query",
            "LoadBalancers[].LoadBalancerName",
            "--output",
            "text",
        ],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print("⚠️ Unable to query load balancers.")
        time.sleep(CHECK_INTERVAL_SECONDS)
        elapsed += CHECK_INTERVAL_SECONDS
        continue

    output = result.stdout.strip()

    if not output:

        print("✅ No AWS Load Balancers remain.")

        alb_deleted = True
        break

    print()
    print(f"⏳ Load Balancers still present: {output}")
    print(f"   Waiting... {elapsed}/{MAX_WAIT_SECONDS} seconds")

    time.sleep(CHECK_INTERVAL_SECONDS)

    elapsed += CHECK_INTERVAL_SECONDS


# =========================================================
# Verify ALB deletion
# =========================================================

if not alb_deleted:

    print()
    print("⚠️ Timeout waiting for Load Balancers to disappear.")
    print()
    print("Current Load Balancers:")

    run(
        [
            "aws",
            "elbv2",
            "describe-load-balancers",
            "--region",
            AWS_REGION,
            "--query",
            "LoadBalancers[].{Name:LoadBalancerName,State:State.Code,DNS:DNSName}",
            "--output",
            "table",
        ],
        allow_failure=True,
    )

    print()
    print("❌ Stopping cleanup.")
    print()
    print("Terraform destroy should NOT run until the ALB")
    print("created by Kubernetes has been removed.")

    sys.exit(1)


# =========================================================
# Uninstall AWS Load Balancer Controller
# =========================================================

print()
print("=" * 70)
print("🗑️ UNINSTALLING AWS LOAD BALANCER CONTROLLER")
print("=" * 70)

helm_check = subprocess.run(
    [
        "helm",
        "status",
        ALB_CONTROLLER_RELEASE,
        "--namespace",
        ALB_CONTROLLER_NAMESPACE,
    ],
    text=True,
    capture_output=True,
)

if helm_check.returncode == 0:

    run(
        [
            "helm",
            "uninstall",
            ALB_CONTROLLER_RELEASE,
            "--namespace",
            ALB_CONTROLLER_NAMESPACE,
        ]
    )

else:

    print("ℹ️ AWS Load Balancer Controller Helm release not found.")


# ---------------------------------------------------------
# Uninstall External Secrets Operator
# ---------------------------------------------------------

print("\n🧹 Uninstalling External Secrets Operator...")

eso_check = subprocess.run(
    [
        "helm",
        "status",
        ESO_HELM_RELEASE,
        "--namespace",
        ESO_NAMESPACE,
    ],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
)

if eso_check.returncode == 0:

    run(
        [
            "helm",
            "uninstall",
            ESO_HELM_RELEASE,
            "--namespace",
            ESO_NAMESPACE,
        ]
    )

    print("✅ External Secrets Operator Helm release removed.")

else:

    print("ℹ️ External Secrets Operator Helm release not found.")


# ---------------------------------------------------------
# Delete External Secrets namespace
# ---------------------------------------------------------

print("\n🧹 Removing External Secrets namespace...")

namespace_check = subprocess.run(
    [
        "kubectl",
        "get",
        "namespace",
        ESO_NAMESPACE,
    ],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
)

if namespace_check.returncode == 0:

    run(
        [
            "kubectl",
            "delete",
            "namespace",
            ESO_NAMESPACE,
            "--ignore-not-found=true",
            "--wait=true",
        ]
    )

    print("✅ External Secrets namespace removed.")

else:

    print("ℹ️ External Secrets namespace does not exist.")


# =========================================================
# Delete ServiceAccount
# =========================================================

print("\n🗑️ Removing ALB Controller ServiceAccount...")

run(
    [
        "kubectl",
        "delete",
        "serviceaccount",
        "aws-load-balancer-controller",
        "--namespace",
        ALB_CONTROLLER_NAMESPACE,
        "--ignore-not-found=true",
    ],
    allow_failure=True,
)


# =========================================================
# Final verification
# =========================================================

print()
print("=" * 70)
print("🔍 FINAL VERIFICATION")
print("=" * 70)

print("\nIngress resources:")

run(
    [
        "kubectl",
        "get",
        "ingress",
        "--all-namespaces",
    ],
    allow_failure=True,
)

print("\nAWS Load Balancers:")

run(
    [
        "aws",
        "elbv2",
        "describe-load-balancers",
        "--region",
        AWS_REGION,
        "--query",
        "LoadBalancers[].{Name:LoadBalancerName,State:State.Code}",
        "--output",
        "table",
    ],
    allow_failure=True,
)


# =========================================================
# Completed
# =========================================================

print()
print("=" * 70)
print("✅ EXTERNAL RESOURCE CLEANUP COMPLETED")
print("=" * 70)

print()
print("The following non-Terraform resources were cleaned up:")
print()
print("  ✅ Kubernetes Ingress")
print("  ✅ Kubernetes-created AWS Load Balancer")
print("  ✅ AWS Load Balancer Controller Helm release")
print("  ✅ ALB Controller ServiceAccount")
print("✅ External Secrets namespace removed.")

print()
print("Terraform destroy can now safely run.")