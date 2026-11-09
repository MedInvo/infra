import argparse
import json
import time

from cleanup_common import (
    NAMESPACE, ARGO_NAMESPACE, run, json_output, verify_aws_and_cluster,
    wait_for_ingress_load_balancers, confirm_execution, say, stop
)

APP_NAMES = [
    "pharma-frontend-dev",
    "pharma-order-service-dev",
    "pharma-product-service-dev",
    "pharma-shared-dev",
]

def main():
    parser = argparse.ArgumentParser(
        description="Delete Argo CD-managed Pharma application resources and wait for ALB cleanup."
    )
    parser.add_argument("--execute", action="store_true", help="Actually delete resources. Without this, only show the plan.")
    parser.add_argument("--skip-namespace", action="store_true", help="Do not delete the pharma-app namespace after Argo CD cleanup.")
    args = parser.parse_args()

    verify_aws_and_cluster()
    confirm_execution(args.execute, "DELETE PHARMA APPLICATION")

    # Capture Ingress DNS before the Application cascade removes the Ingress.
    ing = json_output(["kubectl", "get", "ingress", "-n", NAMESPACE, "-o", "json"])
    dns_names = []
    for item in ing.get("items", []):
        for address in item.get("status", {}).get("loadBalancer", {}).get("ingress", []):
            value = address.get("hostname") or address.get("ip")
            if value:
                dns_names.append(value)

    # Disable automated reconciliation before removing Application objects.
    for app in APP_NAMES:
        exists = run([
            "kubectl", "get", "application", app, "-n", ARGO_NAMESPACE
        ], capture=True, check=False)
        if exists.returncode != 0:
            say(f"Application/{app} not found; skipping.")
            continue
        run([
            "kubectl", "patch", "application", app, "-n", ARGO_NAMESPACE,
            "--type=merge", "-p", '{"spec":{"syncPolicy":{"automated":null}}}'
        ], execute=args.execute)
        # Foreground deletion allows Argo CD's resource finalizer to cascade-delete
        # resources tracked by this Application before the Application disappears.
        run([
            "kubectl", "delete", "application", app, "-n", ARGO_NAMESPACE,
            "--cascade=foreground", "--wait=true", "--timeout=10m"
        ], execute=args.execute)

    if not args.execute:
        say("Dry-run complete. Planned: disable auto-sync, delete the four Argo CD Applications with foreground cascade.")
        say("Then wait for the controller-managed ALB to disappear and delete the app namespace.")
        return

    # Ingress deletion triggers AWS Load Balancer Controller cleanup. Do not manually
    # delete the ALB while Kubernetes still owns it.
    wait_for_ingress_load_balancers(dns_names, timeout=900)

    if not args.skip_namespace:
        exists = run(["kubectl", "get", "namespace", NAMESPACE], capture=True, check=False)
        if exists.returncode == 0:
            run([
                "kubectl", "delete", "namespace", NAMESPACE,
                "--wait=true", "--timeout=10m"
            ])
        else:
            say(f"Namespace/{NAMESPACE} is already absent.")

    say("Application cleanup completed. EKS, node groups, RDS, ECR repositories, IAM, VPC, Route 53 and Terraform state were not touched.")

if __name__ == "__main__":
    main()
