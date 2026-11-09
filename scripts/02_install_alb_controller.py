#!/usr/bin/env python3

import subprocess
import sys

REGION = "us-east-1"
CLUSTER_NAME = "pharma-dev-cluster"
NAMESPACE = "kube-system"
SERVICE_ACCOUNT = "aws-load-balancer-controller"
ROLE_ARN = (
    "arn:aws:iam::259732629629:role/"
    "pharma-medinvo-dev-alb-controller-role"
)
RELEASE_NAME = "aws-load-balancer-controller"
CHART = "eks/aws-load-balancer-controller"
CHART_VERSION = "1.14.0"


def run(cmd, capture=False):
    print(f"\n$ {' '.join(cmd)}", flush=True)

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=capture,
    )

    if capture and result.stdout:
        print(result.stdout.strip())

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise RuntimeError(f"Command failed: {cmd[0]}")

    return result.stdout.strip() if capture else None


def main():
    print("=== AWS Load Balancer Controller Installation ===")

    # 1. Discover the VPC dynamically from EKS.
    vpc_id = run([
        "aws", "eks", "describe-cluster",
        "--name", CLUSTER_NAME,
        "--region", REGION,
        "--query", "cluster.resourcesVpcConfig.vpcId",
        "--output", "text",
    ], capture=True)

    if not vpc_id.startswith("vpc-"):
        raise RuntimeError(f"Unexpected EKS VPC ID: {vpc_id}")

    print(f"Discovered VPC: {vpc_id}")

    # 2. Configure kubectl and verify cluster access.
    run([
        "aws", "eks", "update-kubeconfig",
        "--region", REGION,
        "--name", CLUSTER_NAME,
    ])
    run(["kubectl", "get", "nodes"])

    # 3. Create the ServiceAccount if missing.
    result = subprocess.run(
        [
            "kubectl", "get", "serviceaccount",
            SERVICE_ACCOUNT, "-n", NAMESPACE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        run([
            "kubectl", "create", "serviceaccount",
            SERVICE_ACCOUNT, "-n", NAMESPACE,
        ])

    # 4. Attach the controller's IAM role.
    run([
        "kubectl", "annotate", "serviceaccount",
        SERVICE_ACCOUNT, "-n", NAMESPACE,
        f"eks.amazonaws.com/role-arn={ROLE_ARN}",
        "--overwrite",
    ])

    # 5. Configure Helm repository.
    run([
        "helm", "repo", "add", "eks",
        "https://aws.github.io/eks-charts",
        "--force-update",
    ])
    run(["helm", "repo", "update"])

    # 6. Install/upgrade with explicit values.
    # --reset-values avoids reusing stale values from the old release.
    run([
        "helm", "upgrade", "--install",
        RELEASE_NAME, CHART,
        "--namespace", NAMESPACE,
        "--version", CHART_VERSION,
        "--reset-values",
        "--set", f"clusterName={CLUSTER_NAME}",
        "--set", f"region={REGION}",
        "--set", f"vpcId={vpc_id}",
        "--set", "ingressClass=alb",
        "--set", "serviceAccount.create=false",
        "--set", f"serviceAccount.name={SERVICE_ACCOUNT}",
        "--wait",
        "--timeout", "5m",
    ])

    # 7. Wait for the controller to become healthy.
    try:
        run([
            "kubectl", "rollout", "status",
            f"deployment/{RELEASE_NAME}",
            "-n", NAMESPACE,
            "--timeout=180s",
        ])
    except RuntimeError:
        print("\nController rollout failed. Recent logs:")
        subprocess.run([
            "kubectl", "logs",
            "-n", NAMESPACE,
            f"deployment/{RELEASE_NAME}",
            "--all-pods=true",
            "--tail=100",
        ])
        subprocess.run([
            "kubectl", "get", "pods",
            "-n", NAMESPACE, "-o", "wide",
        ])
        raise

    # 8. Final verification.
    run([
        "kubectl", "get", "deployment",
        RELEASE_NAME, "-n", NAMESPACE,
    ])
    run([
        "kubectl", "get", "pods",
        "-n", NAMESPACE,
        "-l", "app.kubernetes.io/name=aws-load-balancer-controller",
    ])

    print("\n=== Controller installation verified ===")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
