import argparse
import os
from cleanup_common import (
    verify_aws_and_cluster, confirm_execution, run, say, stop
)

# Set these to the exact Helm release names/namespaces shown by: helm list -A
ADDONS = [
    ("ALB controller", "ALB_HELM_RELEASE", "ALB_HELM_NAMESPACE", "kube-system"),
    ("External Secrets Operator", "ESO_HELM_RELEASE", "ESO_HELM_NAMESPACE", "external-secrets"),
    ("Argo CD", "ARGOCD_HELM_RELEASE", "ARGOCD_HELM_NAMESPACE", "argocd"),
]

def main():
    parser = argparse.ArgumentParser(
        description="Optionally uninstall add-ons installed with Helm (not Terraform-managed)."
    )
    parser.add_argument("--execute", action="store_true", help="Actually uninstall configured Helm releases.")
    args = parser.parse_args()

    verify_aws_and_cluster()
    run(["helm", "list", "-A"])
    configured = []
    for label, release_var, namespace_var, default_ns in ADDONS:
        release = os.getenv(release_var, "").strip()
        namespace = os.getenv(namespace_var, default_ns).strip()
        if release:
            configured.append((label, release, namespace))
        else:
            say(f"{label}: not configured; leaving installed. Set {release_var} only after verifying the exact Helm release.")

    if not configured:
        say("No Helm releases configured. Nothing to uninstall.")
        return

    confirm_execution(args.execute, "UNINSTALL PHARMA ADDONS")
    for label, release, namespace in configured:
        say(f"{label}: Helm release={release}, namespace={namespace}")
        run(["helm", "uninstall", release, "--namespace", namespace], execute=args.execute)

    say("Configured add-ons processed. Do not uninstall Argo CD until all Argo CD Applications have been deleted.")
    say("Do not uninstall the AWS Load Balancer Controller until all Ingresses/ALBs it manages are gone.")

if __name__ == "__main__":
    main()
