import argparse

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


def namespace_exists() -> bool:
    result = run(["kubectl", "get", "namespace", NAMESPACE], capture=True, check=False)
    return result.returncode == 0


def capture_ingress_dns() -> list[str]:
    """Capture ALB DNS names before deleting Ingress objects."""
    if not namespace_exists():
        say(f"Namespace/{NAMESPACE} is already absent; no Ingress DNS names to capture.")
        return []

    ingresses = json_output(["kubectl", "get", "ingress", "-n", NAMESPACE, "-o", "json"])
    dns_names = []
    for item in ingresses.get("items", []):
        for address in item.get("status", {}).get("loadBalancer", {}).get("ingress", []):
            value = address.get("hostname") or address.get("ip")
            if value:
                dns_names.append(value)
    return sorted(set(dns_names))


def main():
    parser = argparse.ArgumentParser(
        description="Delete Pharma application resources and wait for controller-managed ALB cleanup."
    )
    parser.add_argument("--execute", action="store_true", help="Actually delete resources. Without this, only show the plan.")
    parser.add_argument("--skip-namespace", action="store_true", help="Do not delete the pharma-app namespace after application cleanup.")
    args = parser.parse_args()

    verify_aws_and_cluster()
    confirm_execution(args.execute, "DELETE PHARMA APPLICATION")

    dns_names = capture_ingress_dns()
    if dns_names:
        say("Captured Ingress load-balancer address(es): " + ", ".join(dns_names))
    else:
        say("No Ingress load-balancer DNS names were found before cleanup.")

    # First remove GitOps owners where they exist. Missing Applications are expected
    # in some recovery scenarios; Ingress cleanup below is deliberately independent.
    for app in APP_NAMES:
        exists = run(["kubectl", "get", "application", app, "-n", ARGO_NAMESPACE],
                     capture=True, check=False)
        if exists.returncode != 0:
            say(f"Application/{app} not found; skipping Argo CD deletion.")
            continue
        run([
            "kubectl", "patch", "application", app, "-n", ARGO_NAMESPACE,
            "--type=merge", "-p", '{"spec":{"syncPolicy":{"automated":null}}}'
        ], execute=args.execute)
        run([
            "kubectl", "delete", "application", app, "-n", ARGO_NAMESPACE,
            "--cascade=foreground", "--wait=true", "--timeout=10m"
        ], execute=args.execute)

    if not args.execute:
        say("DRY-RUN complete. On execution, the script will explicitly delete all Ingresses in the app namespace, wait for their finalizers/controller cleanup, verify they are gone, wait for captured ALBs to disappear, and then delete the namespace.")
        return

    # Critical fallback: never assume Argo CD Application deletion removed Ingresses.
    # The AWS Load Balancer Controller needs the Ingress finalizer to clean up its ALB.
    if namespace_exists():
        say(f"Explicitly deleting every Ingress in namespace {NAMESPACE} so the AWS Load Balancer Controller can clean up owned ALBs.")
        run([
            "kubectl", "delete", "ingress", "--all", "-n", NAMESPACE,
            "--wait=true", "--timeout=15m"
        ])

        remaining = json_output(["kubectl", "get", "ingress", "-n", NAMESPACE, "-o", "json"])
        remaining_items = remaining.get("items", [])
        if remaining_items:
            names = [item.get("metadata", {}).get("name", "<unnamed>") for item in remaining_items]
            stop("Ingress objects remain after deletion request: " + ", ".join(names) +
                 ". Keep the AWS Load Balancer Controller running and inspect Ingress finalizers/controller logs.")
        say("Verified: no Ingress objects remain in the application namespace.")
    else:
        say(f"Namespace/{NAMESPACE} is already absent; skipping Ingress deletion.")

    # Wait only after Kubernetes Ingress deletion/finalizer processing has completed.
    wait_for_ingress_load_balancers(dns_names, timeout=900)

    if not args.skip_namespace:
        if namespace_exists():
            run([
                "kubectl", "delete", "namespace", NAMESPACE,
                "--wait=true", "--timeout=10m"
            ])
        else:
            say(f"Namespace/{NAMESPACE} is already absent.")

    say("Application cleanup completed. EKS, node groups, RDS, ECR repositories, IAM, VPC, Route 53 and Terraform state were not touched.")


if __name__ == "__main__":
    main()
