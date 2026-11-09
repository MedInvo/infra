from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from common import SCRIPT_DIR, say, fail

STEPS = [
    ("01_connect_eks.py", "Connect to existing EKS cluster"),
    ("02_verify_controllers.py", "Verify existing controllers"),
    ("03_apply_argocd_apps.py", "Apply Argo CD project and Applications"),
    ("04_sync_shared.py", "Sync shared resources and verify database Secret"),
    ("05_sync_backends.py", "Sync product and order services"),
    ("06_sync_frontend.py", "Sync frontend"),
    ("07_verify_application.py", "Verify application resources"),
    ("08_verify_ingress.py", "Verify ALB and HTTP response"),
]

def main():
    say("Starting safe, repeatable Pharma EKS application deployment.")
    say("This workflow does NOT run Terraform, create IAM resources, install controllers, delete resources or print Secret values.")
    for filename, description in STEPS:
        script = SCRIPT_DIR / filename
        if not script.is_file():
            fail(f"Required deployment script is missing: {script}")
        say(f"RUNNING: {description}")
        result = subprocess.run([sys.executable, str(script)], check=False)
        if result.returncode != 0:
            fail(f"Stopped at {filename}. Fix the reported issue, then rerun deploy_all.py.")
    say("DEPLOYMENT COMPLETED: all checks passed.")

if __name__ == "__main__":
    main()
