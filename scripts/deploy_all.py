#!/usr/bin/env python3
"""Deploy the Pharma Kubernetes manifests to the current kubectl context."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


NAMESPACE = "pharma-app"
ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = ROOT / "k8s"


def run(command: list[str]) -> None:
    """Run a command, showing it first and stopping on failure."""
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, check=True)


def apply_manifest(filename: str) -> None:
    run(["kubectl", "apply", "-f", str(MANIFESTS / filename)])


def wait_for_deployment(name: str) -> None:
    run([
        "kubectl",
        "rollout",
        "status",
        f"deployment/{name}",
        "--namespace",
        NAMESPACE,
        "--timeout=180s",
    ])


def main() -> int:
    try:
        print("======================================")
        print(" Deploying Pharma Kubernetes Manifests")
        print("======================================")

        # Namespace and configuration must exist before workloads reference them.
        for manifest in ("namespace.yaml", "secret.yaml", "configmap.yaml", "postgres-pvc.yaml"):
            apply_manifest(manifest)

        # Create services before their corresponding workloads.
        for manifest in (
            "postgres-service.yaml",
            "product-service-service.yaml",
            "order-service-service.yaml",
            "frontend-service.yaml",
        ):
            apply_manifest(manifest)

        apply_manifest("postgres-deployment.yaml")
        wait_for_deployment("postgres")

        for manifest in (
            "product-service-deployment.yaml",
            "order-service-deployment.yaml",
            "frontend-deployment.yaml",
        ):
            apply_manifest(manifest)

        for deployment in ("product-service", "order-service", "frontend"):
            wait_for_deployment(deployment)

        print("\n======================================")
        print(" Environment deployed successfully")
        print("======================================")
        run(["kubectl", "get", "pods", "--namespace", NAMESPACE])
        run(["kubectl", "get", "services", "--namespace", NAMESPACE])
        return 0
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nDeployment failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
