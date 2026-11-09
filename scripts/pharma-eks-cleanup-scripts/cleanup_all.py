import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def run_step(script: str, execute: bool):
    command = [sys.executable, str(HERE / script)]
    if execute:
        command.append("--execute")
    print("\n" + "=" * 72)
    print(f"STEP: {script}")
    print("=" * 72, flush=True)
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

def main():
    parser = argparse.ArgumentParser(
        description="Ordered cleanup of Pharma application resources. Terraform infrastructure is excluded."
    )
    parser.add_argument("--execute", action="store_true", help="Perform destructive actions. Default is dry-run.")
    parser.add_argument("--include-addons", action="store_true", help="Also uninstall configured Helm add-ons.")
    parser.add_argument("--include-ecr-images", action="store_true", help="Also empty the three ECR repositories (repositories remain).")
    args = parser.parse_args()

    print("CLEANUP ORDER")
    print("1. Read-only preflight inventory")
    print("2. Delete existing Argo CD Applications with foreground cascade")
    print("3. Explicitly delete all Ingresses and wait for finalizer/controller cleanup")
    print("4. Wait for controller-managed ALB deletion")
    print("5. Delete pharma-app namespace")
    if args.include_addons:
        print("5. Uninstall explicitly configured Helm add-ons (ALB controller, ESO, then Argo CD)")
    if args.include_ecr_images:
        print("6. Empty image manifests/tags from Terraform-managed ECR repositories")
    print("\nTerraform-owned infrastructure is never destroyed by this program.")

    if args.execute:
        print("\nYou selected EXECUTE. The individual scripts will ask for exact confirmation phrases.")
    else:
        print("\nDRY-RUN: no deletion will occur. Add --execute only after reviewing every planned action.")

    run_step("00_preflight.py", False)
    run_step("01_cleanup_application.py", args.execute)

    if args.include_addons:
        # The add-on script is intentionally separate so users must opt in.
        run_step("02_uninstall_addons.py", args.execute)

    if args.include_ecr_images:
        run_step("03_empty_ecr_images.py", args.execute)

    print("\nCleanup sequence finished. Review AWS console and Terraform plan before running the infrastructure destroy workflow.")

if __name__ == "__main__":
    main()
