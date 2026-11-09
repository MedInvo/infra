import argparse

from cleanup_common import (
    AWS_REGION, ECR_REPOSITORIES, run, json_output, verify_aws_and_cluster,
    confirm_execution, say, stop
)

def list_image_ids(repo: str) -> list[dict]:
    result = json_output([
        "aws", "ecr", "list-images", "--repository-name", repo,
        "--region", AWS_REGION, "--filter", "tagStatus=ANY", "--output", "json"
    ])
    # One manifest can be returned once per tag. Delete each digest only once.
    unique = {}
    for image in result.get("imageIds", []):
        key = image.get("imageDigest") or image.get("imageTag")
        if key:
            unique[key] = image
    return list(unique.values())

def main():
    parser = argparse.ArgumentParser(
        description="Delete image manifests/tags from Terraform-managed ECR repositories. Repositories are retained."
    )
    parser.add_argument("--execute", action="store_true", help="Actually delete image IDs.")
    args = parser.parse_args()

    verify_aws_and_cluster()
    # Safety check: do not remove image digests that are still referenced by active pods.
    pods = json_output(["kubectl", "get", "pods", "-A", "-o", "json"]).get("items", [])
    repo_names = set(ECR_REPOSITORIES)
    in_use = []
    for pod in pods:
        phase = pod.get("status", {}).get("phase")
        deleting = pod.get("metadata", {}).get("deletionTimestamp")
        if phase in ("Succeeded", "Failed") or deleting:
            continue
        spec = pod.get("spec", {})
        containers = spec.get("containers", []) + spec.get("initContainers", []) + spec.get("ephemeralContainers", [])
        for container in containers:
            image = container.get("image", "")
            if any(repo in image for repo in repo_names):
                in_use.append(
                    f"{pod.get('metadata', {}).get('namespace')}/{pod.get('metadata', {}).get('name')} -> {image}"
                )
    if in_use:
        stop("ECR images are still referenced by active pods. Clean up those workloads first: " + "; ".join(in_use[:12]))

    inventory = {}
    for repo in ECR_REPOSITORIES:
        check = run([
            "aws", "ecr", "describe-repositories", "--repository-names", repo,
            "--region", AWS_REGION, "--output", "json"
        ], capture=True, check=False)
        if check.returncode != 0:
            say(f"Repository {repo} not found or not accessible; skipping.")
            continue
        image_ids = list_image_ids(repo)
        inventory[repo] = image_ids
        say(f"{repo}: {len(image_ids)} image manifest(s)/tag reference(s) returned by ECR")

    if not args.execute:
        say("Dry-run only. No ECR images were deleted. Re-run with --execute after reviewing the repository list.")
        return

    confirm_execution(True, "EMPTY PHARMA ECR IMAGES")
    for repo, image_ids in inventory.items():
        if not image_ids:
            say(f"{repo}: already empty.")
            continue
        # ECR BatchDeleteImage accepts at most 100 image IDs per request.
        for start in range(0, len(image_ids), 100):
            batch = image_ids[start:start + 100]
            args_list = []
            for image in batch:
                if image.get("imageDigest"):
                    args_list.extend(["--image-ids", f"imageDigest={image['imageDigest']}"])
                elif image.get("imageTag"):
                    args_list.extend(["--image-ids", f"imageTag={image['imageTag']}"])
            if args_list:
                result = run([
                    "aws", "ecr", "batch-delete-image",
                    "--repository-name", repo, "--region", AWS_REGION,
                    *args_list, "--output", "json"
                ], capture=True, check=False)
                if result.returncode != 0:
                    stop(f"Failed deleting images from {repo}. Inspect ECR errors before retrying.")
                # AWS may return per-image failures even when the CLI exit code is zero.
                import json
                payload = json.loads(result.stdout or "{}")
                failures = payload.get("failures", [])
                if failures:
                    stop(f"ECR reported deletion failures in {repo}: {failures[:5]}")
        remaining = list_image_ids(repo)
        if remaining:
            stop(f"{repo} still contains {len(remaining)} image references. Check ECR lifecycle/immutability or retry.")
        say(f"{repo}: image manifests/tags deleted. Repository retained.")

    say("ECR image cleanup complete. ECR repositories were NOT deleted; Terraform/GitHub Actions remains responsible for repository destruction.")

if __name__ == "__main__":
    main()
