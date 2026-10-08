"""Deploy the EKS application path after Terraform has created the foundation.

Run this from a private network that can reach the EKS endpoint:
  AWS_LBC_ROLE_ARN=<terraform output> python3 scripts/deploy_aws.py
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
K8S = ROOT / "k8s"


def run(*command: str, input_text: Optional[str] = None) -> None:
    subprocess.run(command, input=input_text, text=True, check=True)


def main() -> None:
    role_arn = os.environ.get("AWS_LBC_ROLE_ARN")
    cluster_name = os.environ.get("EKS_CLUSTER_NAME", "pharma-devops-dev")
    if not role_arn:
        raise SystemExit("Set AWS_LBC_ROLE_ARN to Terraform output aws_load_balancer_controller_role_arn.")

    template = (K8S / "aws-load-balancer-controller-serviceaccount.yaml.template").read_text()
    service_account = template.replace("${AWS_LBC_ROLE_ARN}", role_arn)

    run("kubectl", "apply", "-f", "-", input_text=service_account)
    run("helm", "repo", "add", "eks", "https://aws.github.io/eks-charts")
    run("helm", "repo", "update")
    run(
        "helm", "upgrade", "--install", "aws-load-balancer-controller",
        "eks/aws-load-balancer-controller", "--namespace", "kube-system",
        "--set", f"clusterName={cluster_name}",
        "--set", "serviceAccount.create=false",
        "--set", "serviceAccount.name=aws-load-balancer-controller",
    )

    # Apply only after application manifests have been migrated from local PostgreSQL to RDS.
    run("kubectl", "apply", "-f", str(K8S / "internal-alb-ingress.yaml"))


if __name__ == "__main__":
    main()
