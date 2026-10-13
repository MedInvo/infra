#!/usr/bin/env python3
"""Safely clean up Kubernetes-created external resources for Pharma DevOps.

Deletes only Ingress resources in the configured application namespace, waits for
ALBs recorded in those Ingress status objects, then uninstalls the ALB controller
and ESO Helm releases. It does NOT destroy Terraform resources, EKS, RDS, Route 53,
ECR, IAM roles, or AWS Secrets Manager secrets.
"""
import json
import shutil
import subprocess
import sys
import time

AWS_REGION = "us-east-1"
EKS_CLUSTER_NAME = "pharma-dev-cluster"
APPLICATION_NAMESPACE = "pharma-app"

ALB_CONTROLLER_NAMESPACE = "kube-system"
ALB_CONTROLLER_RELEASE = "aws-load-balancer-controller"
ALB_CONTROLLER_SERVICE_ACCOUNT = "aws-load-balancer-controller"

ESO_NAMESPACE = "external-secrets"
ESO_HELM_RELEASE = "external-secrets"

MAX_WAIT_SECONDS = 600
CHECK_INTERVAL_SECONDS = 10
DELETE_ESO_NAMESPACE = True


def run(command, *, allow_failure=False, timeout=120):
    print("\\n" + "=" * 78)
    print("$ " + " ".join(command))
    print("=" * 78)
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"ERROR: command timed out after {timeout} seconds.")
        if allow_failure:
            return None
        sys.exit(1)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        if allow_failure:
            print("WARNING: command failed; continuing only where safe.")
            return result
        print("ERROR: command failed; stopping cleanup.")
        sys.exit(result.returncode)
    return result


def require_commands():
    missing = [name for name in ("aws", "kubectl", "helm") if not shutil.which(name)]
    if missing:
        print("ERROR: required command(s) not found: " + ", ".join(missing))
        sys.exit(1)


def get_ingresses():
    result = run(
        ["kubectl", "get", "ingress", "--namespace", APPLICATION_NAMESPACE, "-o", "json"],
        allow_failure=True,
    )
    if result is None or result.returncode != 0:
        print("ERROR: unable to read Ingress resources; refusing to continue.")
        sys.exit(1)
    try:
        return json.loads(result.stdout).get("items", [])
    except json.JSONDecodeError:
        print("ERROR: kubectl returned invalid JSON; refusing to continue.")
        sys.exit(1)


def get_ingress_alb_dns_names(ingresses):
    names = set()
    for ingress in ingresses:
        entries = ingress.get("status", {}).get("loadBalancer", {}).get("ingress", [])
        for entry in entries:
            hostname = entry.get("hostname")
            if hostname:
                names.add(hostname.rstrip(".").lower())
    return names


def get_load_balancers():
    result = run(
        ["aws", "elbv2", "describe-load-balancers", "--region", AWS_REGION, "--output", "json"],
        allow_failure=True,
    )
    if result is None or result.returncode != 0:
        print("ERROR: unable to query AWS Load Balancers; cannot verify cleanup.")
        sys.exit(1)
    try:
        return json.loads(result.stdout).get("LoadBalancers", [])
    except json.JSONDecodeError:
        print("ERROR: AWS returned invalid JSON.")
        sys.exit(1)


def matching_application_albs(dns_names):
    if not dns_names:
        return []
    return [
        lb for lb in get_load_balancers()
        if lb.get("Type") == "application"
        and (lb.get("DNSName") or "").rstrip(".").lower() in dns_names
    ]


def wait_for_application_albs(dns_names):
    # Never block on unrelated load balancers in the AWS account.
    if not dns_names:
        print(
            "\\nNo ALB DNS hostname was recorded in the Ingress status. "
            "Cannot safely identify an ALB by DNS. Check AWS and controller logs "
            "manually if an ALB may have been created before status was populated."
        )
        return True

    print("\\nWaiting for ALB(s) associated with the app Ingress:")
    for name in sorted(dns_names):
        print("  - " + name)

    elapsed = 0
    while elapsed <= MAX_WAIT_SECONDS:
        remaining = matching_application_albs(dns_names)
        if not remaining:
            print("Confirmed: recorded application ALB(s) no longer exist.")
            return True
        print(
            f"Still waiting ({elapsed}/{MAX_WAIT_SECONDS}s): "
            + ", ".join(lb.get("LoadBalancerName", "<unnamed>") for lb in remaining)
        )
        time.sleep(CHECK_INTERVAL_SECONDS)
        elapsed += CHECK_INTERVAL_SECONDS

    print("ERROR: timed out waiting for the application's ALB(s).")
    for lb in matching_application_albs(dns_names):
        print(f"  Name: {lb.get('LoadBalancerName')}; DNS: {lb.get('DNSName')}; "
              f"state: {lb.get('State', {}).get('Code')}")
    print("Stopping. Keep the controller installed until ALB cleanup is resolved.")
    return False


def helm_release_exists(release, namespace):
    result = run(
        ["helm", "status", release, "--namespace", namespace],
        allow_failure=True,
    )
    return result is not None and result.returncode == 0


def cleanup_eso_namespace():
    if not DELETE_ESO_NAMESPACE:
        print("ESO namespace deletion disabled by configuration.")
        return

    exists = run(
        ["kubectl", "get", "namespace", ESO_NAMESPACE, "-o", "name"],
        allow_failure=True,
    )
    if exists is None or exists.returncode != 0:
        print(f"ESO namespace '{ESO_NAMESPACE}' does not exist; skipping.")
        return

    # Keep namespace if any workload or ESO custom resources remain.
    resources = run(
        ["kubectl", "get", "all,externalsecrets,secretstores,clustersecretstores",
         "--namespace", ESO_NAMESPACE, "-o", "name"],
        allow_failure=True,
    )
    if resources is None or resources.returncode != 0:
        print("WARNING: unable to inspect ESO namespace; leaving it in place.")
        return

    remaining = [line.strip() for line in resources.stdout.splitlines() if line.strip()]
    if remaining:
        print("WARNING: ESO namespace still contains resources; leaving it in place:")
        for resource in remaining:
            print("  - " + resource)
        return

    run(["kubectl", "delete", "namespace", ESO_NAMESPACE, "--wait=true", "--timeout=180s"],
        timeout=200)
    print(f"ESO namespace '{ESO_NAMESPACE}' deleted.")


def main():
    print("=" * 78)
    print("PHASE 6.09 - SAFE EXTERNAL RESOURCE CLEANUP")
    print("=" * 78)
    print(f"Region: {AWS_REGION} | EKS: {EKS_CLUSTER_NAME}")
    print(f"Application namespace: {APPLICATION_NAMESPACE}")
    print(f"ALB controller: {ALB_CONTROLLER_RELEASE} in {ALB_CONTROLLER_NAMESPACE}")
    print(f"ESO: {ESO_HELM_RELEASE} in {ESO_NAMESPACE}")
    print("\\nThis script deletes app Ingress resources, their recorded ALB(s), and the")
    print("ALB controller/ESO Helm releases. It does not destroy Terraform infrastructure,")
    print("RDS, Route 53 records, ECR, IAM roles, or Secrets Manager secrets.")

    require_commands()
    confirmation = input("\\nType CLEANUP-PHARMA-INGRESS to continue: ").strip()
    if confirmation != "CLEANUP-PHARMA-INGRESS":
        print("Confirmation did not match. No cleanup performed.")
        return

    run(["aws", "sts", "get-caller-identity"])
    run(["aws", "eks", "update-kubeconfig", "--region", AWS_REGION, "--name", EKS_CLUSTER_NAME])
    run(["kubectl", "cluster-info"])
    run(["kubectl", "get", "nodes", "-o", "wide"])

    # Capture ALB DNS names before deleting the Ingress resources.
    ingresses = get_ingresses()
    print(f"\\nFound {len(ingresses)} Ingress resource(s) in {APPLICATION_NAMESPACE}.")
    for item in ingresses:
        name = item.get("metadata", {}).get("name", "<unnamed>")
        print(f"  - {name}")
    alb_dns_names = get_ingress_alb_dns_names(ingresses)
    if alb_dns_names:
        print("ALB DNS names recorded in Ingress status:")
        for name in sorted(alb_dns_names):
            print("  - " + name)
    elif ingresses:
        print(
            "ERROR: Ingress resources exist but none has an ALB DNS hostname in status. "
            "To avoid orphaning a possibly-created ALB, this script will not delete "
            "the Ingress or uninstall the controller. Check Ingress events and the "
            "AWS Load Balancer Controller logs, then rerun after the ALB is identified."
        )
        sys.exit(1)

    if ingresses:
        run(["kubectl", "delete", "ingress", "--all",
             "--namespace", APPLICATION_NAMESPACE,
             "--wait=true", "--timeout=180s"], timeout=200)
    else:
        print("No application Ingress resources to delete.")

    # If Ingresses existed, wait for only their recorded ALBs. If no Ingress existed,
    # there is no application ALB to infer from this namespace; do not use a region-wide
    # load-balancer query as a deletion gate.
    if ingresses and not wait_for_application_albs(alb_dns_names):
        sys.exit(1)
    if not ingresses:
        print("No app Ingress existed; skipping ALB wait and leaving unrelated ALBs untouched.")

    if helm_release_exists(ALB_CONTROLLER_RELEASE, ALB_CONTROLLER_NAMESPACE):
        run(["helm", "uninstall", ALB_CONTROLLER_RELEASE,
             "--namespace", ALB_CONTROLLER_NAMESPACE, "--wait", "--timeout", "180s"],
            timeout=200)
    else:
        print("ALB controller Helm release not found; skipping.")

    run(["kubectl", "delete", "serviceaccount", ALB_CONTROLLER_SERVICE_ACCOUNT,
         "--namespace", ALB_CONTROLLER_NAMESPACE, "--ignore-not-found=true"],
        allow_failure=True)

    if helm_release_exists(ESO_HELM_RELEASE, ESO_NAMESPACE):
        run(["helm", "uninstall", ESO_HELM_RELEASE,
             "--namespace", ESO_NAMESPACE, "--wait", "--timeout", "180s"],
            timeout=200)
    else:
        print("ESO Helm release not found; skipping.")

    cleanup_eso_namespace()

    print("\\n" + "=" * 78)
    print("CLEANUP SCRIPT FINISHED")
    print("=" * 78)
    print("Review output and verify AWS resources before running Terraform destroy.")
    print("No Terraform-managed infrastructure or AWS Secrets Manager secrets were deleted.")


if __name__ == "__main__":
    main()
