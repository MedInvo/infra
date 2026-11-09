from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EXPECTED_ACCOUNT = os.getenv("EXPECTED_AWS_ACCOUNT", "259732629629")
EKS_CLUSTER = os.getenv("EKS_CLUSTER", "pharma-dev-cluster")
NAMESPACE = os.getenv("APP_NAMESPACE", "pharma-app")
ARGO_NAMESPACE = os.getenv("ARGO_NAMESPACE", "argocd")
ECR_REPOSITORIES = [
    "pharma-medinvo-dev-frontend",
    "pharma-medinvo-dev-order-service",
    "pharma-medinvo-dev-product-service",
]

def say(message: str) -> None:
    print(f"\n[pharma-cleanup] {message}", flush=True)

def stop(message: str, code: int = 1) -> None:
    print(f"\n[STOP] {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)

def run(args: list[str], *, capture: bool = False, check: bool = True,
        execute: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    command = " ".join(args)
    say(("$ " if execute else "[DRY-RUN] $ ") + command)
    if not execute:
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
    try:
        result = subprocess.run(args, text=True, capture_output=capture,
                                check=False, timeout=timeout)
    except FileNotFoundError:
        stop(f"Required command not found: {args[0]}. Install it and retry.")
    except subprocess.TimeoutExpired:
        stop(f"Command timed out: {command}")
    if capture and result.stdout:
        print(result.stdout, end="", flush=True)
    if capture and result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if check and result.returncode != 0:
        stop(f"Command failed with exit code {result.returncode}: {command}")
    return result

def json_output(args: list[str]) -> Any:
    result = run(args, capture=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        stop(f"Could not parse JSON from {' '.join(args)}: {exc}")

def verify_aws_and_cluster() -> None:
    ident = json_output(["aws", "sts", "get-caller-identity", "--output", "json"])
    account = ident.get("Account")
    arn = ident.get("Arn", "unknown")
    if account != EXPECTED_ACCOUNT:
        stop(f"AWS account mismatch. Expected {EXPECTED_ACCOUNT}, got {account}. No cleanup performed.")
    say(f"AWS account verified: {account}; identity: {arn}")

    cluster = json_output([
        "aws", "eks", "describe-cluster", "--name", EKS_CLUSTER,
        "--region", AWS_REGION, "--output", "json"
    ]).get("cluster", {})
    status = cluster.get("status")
    if status != "ACTIVE":
        stop(f"EKS cluster {EKS_CLUSTER} is not ACTIVE (status={status}).")
    say(f"EKS cluster verified: {EKS_CLUSTER} ({status})")

    context = run(["kubectl", "config", "current-context"], capture=True).stdout.strip()
    if EKS_CLUSTER not in context:
        stop(f"Current kubectl context does not appear to be {EKS_CLUSTER}: {context}")
    say(f"kubectl context verified: {context}")

def wait_for_ingress_load_balancers(dns_names: list[str], timeout: int = 900) -> None:
    """Wait for controller-managed ALBs to disappear after their Ingresses are deleted."""
    if not dns_names:
        say("No Ingress load-balancer DNS names were found; no ALB wait is needed.")
        return
    deadline = time.time() + timeout
    pending = set(dns_names)
    while pending and time.time() < deadline:
        for dns in list(pending):
            result = run([
                "aws", "elbv2", "describe-load-balancers",
                "--region", AWS_REGION, "--query",
                f"LoadBalancers[?DNSName=='{dns}'].LoadBalancerArn | [0]",
                "--output", "text"
            ], capture=True, check=False)
            arn = result.stdout.strip()
            if not arn or arn == "None":
                say(f"ALB deleted: {dns}")
                pending.remove(dns)
        if pending:
            say("Waiting for AWS Load Balancer Controller to finish deleting: " + ", ".join(sorted(pending)))
            time.sleep(15)
    if pending:
        stop("These ALBs still exist after waiting: " + ", ".join(sorted(pending)) +
             ". Do not delete them blindly. Check Ingress, TargetGroupBinding and controller logs.")

def confirm_execution(execute: bool, phrase: str) -> None:
    if not execute:
        say("DRY-RUN only. Nothing was deleted. Re-run with --execute to perform this step.")
        return
    print(f"\nThis action is destructive. Type exactly: {phrase}")
    answer = input("> ").strip()
    if answer != phrase:
        stop("Confirmation did not match. No action taken.")
