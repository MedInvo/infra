#!/usr/bin/env python3

import subprocess
import sys

REGION = "us-east-1"
CLUSTER_NAME = "pharma-dev-cluster"
NAMESPACE = "kube-system"
SERVICE_ACCOUNT = "aws-load-balancer-controller"
ROLE_ARN = "arn:aws:iam::259732629629:role/pharma-medinvo-dev-alb-controller-role"
CHART_VERSION = "1.14.0"


def run(cmd):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        print(f"\nCommand failed: {' '.join(cmd)}")
        sys.exit(result.returncode)


def main():
    print("=== AWS Load Balancer Controller Installation ===")

    # 1. Configure kubectl for EKS
    run([
        "aws", "eks", "update-kubeconfig",
        "--region", REGION,
        "--name", CLUSTER_NAME
    ])

    # 2. Verify cluster access
    run(["kubectl", "get", "nodes"])

    # 3. Create ServiceAccount if it does not already exist
    result = subprocess.run(
        [
            "kubectl", "get", "serviceaccount",
            SERVICE_ACCOUNT,
            "-n", NAMESPACE
        ],
        text=True
    )

    if result.returncode != 0:
        run([
            "kubectl", "create", "serviceaccount",
            SERVICE_ACCOUNT,
            "-n", NAMESPACE
        ])
    else:
        print("ServiceAccount already exists. Skipping creation.")

    # 4. Attach IAM role to ServiceAccount
    run([
        "kubectl", "annotate", "serviceaccount",
        SERVICE_ACCOUNT,
        "-n", NAMESPACE,
        f"eks.amazonaws.com/role-arn={ROLE_ARN}",
        "--overwrite"
    ])

    # 5. Verify ServiceAccount
    run([
        "kubectl", "get", "serviceaccount",
        SERVICE_ACCOUNT,
        "-n", NAMESPACE,
        "-o", "yaml"
    ])

    # 6. Add/update AWS EKS Helm repository
    run([
        "helm", "repo", "add",
        "eks",
        "https://aws.github.io/eks-charts"
    ])

    run(["helm", "repo", "update"])

    # 7. Install or upgrade AWS Load Balancer Controller
    run([
        "helm", "upgrade", "--install",
        "aws-load-balancer-controller",
        "eks/aws-load-balancer-controller",
        "-n", NAMESPACE,
        "--set", f"clusterName={CLUSTER_NAME}",
        "--set", "serviceAccount.create=false",
        "--set", f"serviceAccount.name={SERVICE_ACCOUNT}",
        "--version", CHART_VERSION
    ])

    # 8. Verify deployment
    run([
        "kubectl", "get", "deployment",
        "aws-load-balancer-controller",
        "-n", NAMESPACE
    ])

    # 9. Verify pods
    run([
        "kubectl", "get", "pods",
        "-n", NAMESPACE
    ])

    print("\n=== AWS Load Balancer Controller installation completed ===")


if __name__ == "__main__":
    main()
