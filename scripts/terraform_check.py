import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = PROJECT_ROOT / "terraform" / "environments" / "dev"


def run(command):
    print()
    print("=" * 70)
    print("$", " ".join(command))
    print("=" * 70)

    result = subprocess.run(
        command,
        cwd=TERRAFORM_DIR,
        text=True,
    )

    if result.returncode != 0:
        print()
        print("❌ Command failed.")
        sys.exit(result.returncode)

    print("✅ Command completed successfully.")


run(["terraform", "fmt", "-recursive"])
run(["terraform", "init"])
run(["terraform", "validate"])

print()
print("Next command:")
print(f"  cd {TERRAFORM_DIR}")
print("  terraform plan")