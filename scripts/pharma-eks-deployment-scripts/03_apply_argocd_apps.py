from common import GITOPS_DIR, ARGO_NAMESPACE, fail, run, say

def main():
    say("Step 3/8: Apply the Argo CD project and Application definitions.")
    project = GITOPS_DIR / "argocd" / "projects" / "pharma-project.yaml"
    app_dir = GITOPS_DIR / "argocd" / "applications"
    app_files = [
        "pharma-shared-dev.yaml",
        "pharma-product-service-dev.yaml",
        "pharma-order-service-dev.yaml",
        "pharma-frontend-dev.yaml",
    ]
    if not project.is_file():
        fail(f"Argo CD project manifest not found: {project}")
    run(["kubectl", "apply", "-f", str(project)])
    for filename in app_files:
        path = app_dir / filename
        if not path.is_file():
            fail(f"Argo CD Application manifest not found: {path}")
        run(["kubectl", "apply", "-f", str(path)])
    run(["kubectl", "get", "applications", "-n", ARGO_NAMESPACE])
    say("Argo CD project and Application definitions applied. No application resources were deleted.")

if __name__ == "__main__":
    main()
