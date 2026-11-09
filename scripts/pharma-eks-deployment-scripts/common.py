from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EKS_CLUSTER = os.getenv("EKS_CLUSTER", "pharma-dev-cluster")
NAMESPACE = os.getenv("APP_NAMESPACE", "pharma-app")
ARGO_NAMESPACE = os.getenv("ARGO_NAMESPACE", "argocd")
GITOPS_DIR_NAME = os.getenv("GITOPS_DIR_NAME", "gitops")

# This script bundle is intended to live at:
# <repo-root>/infra/scripts/deployment/
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
GITOPS_DIR = REPO_ROOT / GITOPS_DIR_NAME

ARGO_APPS = [
    "pharma-shared-dev",
    "pharma-product-service-dev",
    "pharma-order-service-dev",
    "pharma-frontend-dev",
]

def say(message: str) -> None:
    print(f"\n[pharma-deploy] {message}", flush=True)

def fail(message: str, code: int = 1) -> None:
    print(f"\n[ERROR] {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)

def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    say("$ " + " ".join(args))
    try:
        result = subprocess.run(
            args,
            text=True,
            check=False,
            capture_output=capture,
            timeout=timeout,
        )
    except FileNotFoundError:
        fail(f"Required command not found: {args[0]}. Install it and ensure it is on PATH.")
    except subprocess.TimeoutExpired:
        fail(f"Command timed out: {' '.join(args)}")
    if capture and result.stdout:
        print(result.stdout, end="", flush=True)
    if capture and result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if check and result.returncode != 0:
        fail(f"Command failed with exit code {result.returncode}: {' '.join(args)}")
    return result

def output_json(args: list[str]) -> Any:
    result = run(args, capture=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"Expected JSON from command, but could not parse it: {exc}")

def wait_until(description: str, predicate, timeout_seconds: int = 180, interval: int = 5) -> Any:
    say(f"Waiting for: {description} (timeout {timeout_seconds}s)")
    deadline = time.time() + timeout_seconds
    last_value = None
    while time.time() < deadline:
        last_value = predicate()
        if last_value:
            say(f"Ready: {description}")
            return last_value
        time.sleep(interval)
    fail(f"Timed out waiting for: {description}. Last observed value: {last_value}")

def check_aws_identity() -> None:
    identity = output_json(["aws", "sts", "get-caller-identity", "--output", "json"])
    arn = identity.get("Arn", "unknown")
    account = identity.get("Account", "unknown")
    say(f"AWS identity OK. Account={account}, ARN={arn}")

def check_nodes_ready() -> None:
    nodes = output_json(["kubectl", "get", "nodes", "-o", "json"])
    items = nodes.get("items", [])
    if not items:
        fail("EKS returned no nodes. Check cluster status and IAM/EKS access.")
    not_ready = []
    for node in items:
        name = node.get("metadata", {}).get("name", "unknown")
        ready = any(
            c.get("type") == "Ready" and c.get("status") == "True"
            for c in node.get("status", {}).get("conditions", [])
        )
        if not ready:
            not_ready.append(name)
    if not_ready:
        fail("These EKS nodes are not Ready: " + ", ".join(not_ready))
    say(f"All {len(items)} EKS node(s) are Ready.")

def pods_ready(namespace: str, name_filter: str | None = None) -> bool:
    data = output_json(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])
    pods = data.get("items", [])
    if name_filter:
        pods = [
            p for p in pods
            if name_filter in p.get("metadata", {}).get("name", "")
        ]
    active = [
        p for p in pods
        if p.get("status", {}).get("phase") not in ("Succeeded", "Failed")
        and not p.get("metadata", {}).get("deletionTimestamp")
    ]
    if not active:
        return False
    for pod in active:
        status = pod.get("status", {})
        if status.get("phase") != "Running":
            return False
        statuses = status.get("containerStatuses", [])
        if not statuses or not all(s.get("ready", False) for s in statuses):
            return False
    return True

def wait_for_pods(namespace: str, name_filter: str | None = None, timeout: int = 180) -> None:
    label = f"pods in namespace {namespace}"
    if name_filter:
        label += f" matching {name_filter}"
    wait_until(label, lambda: pods_ready(namespace, name_filter), timeout_seconds=timeout)

def sync_application(app_name: str, timeout: int = 300) -> None:
    # This requests a normal Argo CD sync. It does not delete or recreate resources.
    patch = '{"operation":{"sync":{}}}'
    run([
        "kubectl", "patch", "application", app_name,
        "-n", ARGO_NAMESPACE, "--type", "merge", "-p", patch
    ])

    def synced_and_healthy():
        app = output_json([
            "kubectl", "get", "application", app_name,
            "-n", ARGO_NAMESPACE, "-o", "json"
        ])
        status = app.get("status", {})
        sync_status = status.get("sync", {}).get("status")
        health_status = status.get("health", {}).get("status")
        operation = status.get("operationState", {})
        phase = operation.get("phase")
        message = operation.get("message", "")
        if phase in ("Failed", "Error"):
            fail(f"Argo CD sync failed for {app_name}: {message}")
        if sync_status == "Synced" and health_status == "Healthy":
            return True
        return False

    wait_until(
        f"Argo CD application {app_name} to become Synced and Healthy",
        synced_and_healthy,
        timeout_seconds=timeout,
    )

def wait_for_deployments(namespace: str, timeout: int = 300) -> None:
    data = output_json(["kubectl", "get", "deployments", "-n", namespace, "-o", "json"])
    deployments = data.get("items", [])
    if not deployments:
        fail(f"No Deployments found in namespace {namespace}.")
    for deployment in deployments:
        name = deployment["metadata"]["name"]
        say(f"Waiting for Deployment/{name}")
        run([
            "kubectl", "rollout", "status",
            f"deployment/{name}", "-n", namespace,
            f"--timeout={timeout}s"
        ])

def verify_database_secret() -> None:
    es = output_json([
        "kubectl", "get", "externalsecret", "pharma-db-secret",
        "-n", NAMESPACE, "-o", "json"
    ])
    conditions = es.get("status", {}).get("conditions", [])
    ready = any(
        c.get("type") == "Ready" and c.get("status") == "True"
        for c in conditions
    )
    if not ready:
        fail("ExternalSecret pharma-db-secret is not Ready=True. Inspect: kubectl describe externalsecret pharma-db-secret -n pharma-app")
    secret = output_json([
        "kubectl", "get", "secret", "postgres-secret",
        "-n", NAMESPACE, "-o", "json"
    ])
    keys = set(secret.get("data", {}).keys())
    required = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
    missing = required - keys
    if missing:
        fail("Kubernetes Secret postgres-secret is missing keys: " + ", ".join(sorted(missing)))
    # Never print Secret values.
    say("ExternalSecret is Ready=True and postgres-secret contains all three required keys (values not displayed).")

def verify_target_groups(timeout: int = 180) -> None:
    def all_healthy():
        bindings = output_json([
            "kubectl", "get", "targetgroupbindings", "-n", NAMESPACE, "-o", "json"
        ]).get("items", [])
        if not bindings:
            return False
        for binding in bindings:
            arn = binding.get("spec", {}).get("targetGroupARN")
            if not arn:
                return False
            result = output_json([
                "aws", "elbv2", "describe-target-health",
                "--target-group-arn", arn,
                "--region", AWS_REGION,
                "--output", "json"
            ])
            targets = result.get("TargetHealthDescriptions", [])
            if not targets:
                return False
            if any(t.get("TargetHealth", {}).get("State") != "healthy" for t in targets):
                return False
        return True
    wait_until("all TargetGroupBinding targets to become healthy", all_healthy, timeout_seconds=timeout)

def verify_ingress_http(timeout: int = 180) -> None:
    def get_address():
        data = output_json(["kubectl", "get", "ingress", "-n", NAMESPACE, "-o", "json"])
        for ingress in data.get("items", []):
            lb = ingress.get("status", {}).get("loadBalancer", {}).get("ingress", [])
            if lb:
                return lb[0].get("hostname") or lb[0].get("ip")
        return None

    address = wait_until("Ingress to receive an ALB address", get_address, timeout_seconds=timeout)
    if not address:
        fail("Ingress has no ALB address.")
    say(f"ALB address: {address}")
    result = run([
        "curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
        f"http://{address}/"
    ], capture=True, check=False, timeout=30)
    code = (result.stdout or "").strip()
    if result.returncode != 0 or not code.startswith(("2", "3")):
        fail(f"ALB HTTP check failed. HTTP status={code or 'no response'}. Check Ingress, target health and frontend logs.")
    say(f"ALB HTTP check succeeded with status {code}.")
