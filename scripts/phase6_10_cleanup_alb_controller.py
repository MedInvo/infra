
#!/usr/bin/env python3

import subprocess
import sys

NAMESPACE = "kube-system"
RELEASE_NAME = "aws-load-balancer-controller"
SERVICE_ACCOUNT = "aws-load-balancer-controller"


def run(cmd, check=True):
    print(f"\n$ {' '.join(cmd)}", flush=True)

    result = subprocess.run(cmd, text=True)

    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    return result.returncode


def main():
    print("=== AWS Load Balancer Controller Cleanup ===")
    print("This removes the Helm release and ServiceAccount.")
    print("It does NOT delete the EKS cluster, VPC, RDS, ECR, or IAM role.")

    confirmation = input(
        "\nType CLEANUP-ALB to continue: "
    ).strip()

    if confirmation != "CLEANUP-ALB":
        print("Cancelled. No resources were deleted.")
        return

    # 1. Check Kubernetes access.
    run(["kubectl", "get", "nodes"])

    # 2. Uninstall Helm release if present.
    result = run([
        "helm", "status", RELEASE_NAME,
        "--namespace", NAMESPACE,
    ], check=False)

    if result == 0:
        run([
            "helm", "uninstall", RELEASE_NAME,
            "--namespace", NAMESPACE,
        ])
    else:
        print("Helm release not found; skipping uninstall.")

    # 3. Delete ServiceAccount if present.
    result = run([
        "kubectl", "get", "serviceaccount",
        SERVICE_ACCOUNT, "-n", NAMESPACE,
    ], check=False)

    if result == 0:
        run([
            "kubectl", "delete", "serviceaccount",
            SERVICE_ACCOUNT, "-n", NAMESPACE,
        ])
    else:
        print("ServiceAccount not found; skipping deletion.")

    # 4. Verify cleanup.
    print("\n=== Verification ===")

    run([
        "kubectl", "get", "deployment",
        RELEASE_NAME, "-n", NAMESPACE,
    ], check=False)

    run([
        "kubectl", "get", "serviceaccount",
        SERVICE_ACCOUNT, "-n", NAMESPACE,
    ], check=False)

    print("\nCleanup commands completed.")
    print("IAM role and core AWS infrastructure were retained.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
