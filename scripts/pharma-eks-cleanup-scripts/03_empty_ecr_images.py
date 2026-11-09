import argparse
import json
import time

from cleanup_common import (
    AWS_REGION,
    ECR_REPOSITORIES,
    run,
    json_output,
    verify_aws_and_cluster,
    confirm_execution,
    say,
    stop,
)

MAX_IMAGES_PER_BATCH = 100
MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 5


def list_image_ids(repo: str) -> list[dict]:
    """Return unique ECR image manifests, deduplicated by digest."""

    result = json_output(
        [
            "aws",
            "ecr",
            "list-images",
            "--repository-name",
            repo,
            "--region",
            AWS_REGION,
            "--filter",
            "tagStatus=ANY",
            "--output",
            "json",
        ]
    )

    unique_images = {}

    for image in result.get("imageIds", []):
        digest = image.get("imageDigest")

        if digest:
            unique_images[digest] = {"imageDigest": digest}
        elif image.get("imageTag"):
            unique_images[image["imageTag"]] = {"imageTag": image["imageTag"]}

    return list(unique_images.values())


def check_active_pods():
    """Prevent deletion if application pods still reference these ECR images."""

    pods = json_output(["kubectl", "get", "pods", "-A", "-o", "json"]).get("items", [])

    in_use = []

    for pod in pods:
        status = pod.get("status", {}).get("phase")
        deleting = pod.get("metadata", {}).get("deletionTimestamp")

        if status in ("Succeeded", "Failed") or deleting:
            continue

        spec = pod.get("spec", {})

        containers = (
            spec.get("containers", [])
            + spec.get("initContainers", [])
            + spec.get("ephemeralContainers", [])
        )

        for container in containers:
            image = container.get("image", "")

            for repo in ECR_REPOSITORIES:
                if f"/{repo}:" in image or f"/{repo}@" in image:
                    in_use.append(
                        f"{pod['metadata'].get('namespace')}/"
                        f"{pod['metadata'].get('name')} -> {image}"
                    )

    if in_use:
        stop(
            "ECR images are still referenced by active Kubernetes pods:\n"
            + "\n".join(in_use[:20])
            + "\nClean up application workloads before deleting images."
        )


def delete_image_batch(repo: str, images: list[dict]):
    """Delete a batch of up to 100 image manifests."""

    image_id_args = []

    for image in images:
        if image.get("imageDigest"):
            image_id_args.append(f"imageDigest={image['imageDigest']}")
        elif image.get("imageTag"):
            image_id_args.append(f"imageTag={image['imageTag']}")

    if not image_id_args:
        return

    command = [
        "aws",
        "ecr",
        "batch-delete-image",
        "--repository-name",
        repo,
        "--region",
        AWS_REGION,
        "--image-ids",
        *image_id_args,
        "--output",
        "json",
    ]

    result = run(command, capture=True, check=False)

    if result.returncode != 0:
        say(f"WARNING: AWS CLI deletion request failed for {repo}.")
        return

    try:
        response = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        stop(f"Could not parse AWS ECR deletion response for {repo}.")

    deleted = response.get("imageIds", [])
    failures = response.get("failures", [])

    say(f"{repo}: AWS deleted {len(deleted)} image reference(s).")

    for failure in failures:
        image_id = failure.get("imageId", {})
        reason = failure.get("failureReason", "Unknown")
        detail = failure.get("failureCode", "Unknown")
        say(f"Deletion warning: {image_id} | " f"{detail} | {reason}")


def clean_repository(repo: str):
    """Delete every image manifest and verify that the repository is empty."""

    say(f"Starting cleanup: {repo}")

    for attempt in range(1, MAX_RETRIES + 1):

        images = list_image_ids(repo)

        if not images:
            say(f"{repo}: repository is EMPTY.")
            return

        say(
            f"{repo}: {len(images)} unique image manifest(s) found. "
            f"Attempt {attempt}/{MAX_RETRIES}."
        )

        for start in range(0, len(images), MAX_IMAGES_PER_BATCH):
            batch = images[start : start + MAX_IMAGES_PER_BATCH]

            delete_image_batch(repo, batch)

        remaining = list_image_ids(repo)

        if not remaining:
            say(f"{repo}: ALL image versions and tags deleted.")
            return

        say(f"{repo}: {len(remaining)} image manifest(s) remain.")

        if attempt < MAX_RETRIES:
            say(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
            time.sleep(RETRY_DELAY_SECONDS)

    remaining = list_image_ids(repo)

    if remaining:
        examples = [
            image.get("imageDigest") or image.get("imageTag")
            for image in remaining[:10]
        ]

        stop(
            f"{repo} still contains {len(remaining)} image manifest(s) "
            f"after {MAX_RETRIES} attempts. "
            f"Examples: {examples}. "
            "Review the AWS ECR deletion failure reasons."
        )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Delete all image versions and tags from Pharma ECR "
            "repositories. ECR repositories are retained."
        )
    )

    parser.add_argument(
        "--execute", action="store_true", help="Actually delete ECR images."
    )

    args = parser.parse_args()

    # Verify AWS account, EKS cluster and kubectl context.
    verify_aws_and_cluster()

    # Protect images currently used by active pods.
    check_active_pods()

    # Check repositories and collect inventory.
    inventory = {}

    say("Checking Pharma ECR repositories...")

    for repo in ECR_REPOSITORIES:

        result = run(
            [
                "aws",
                "ecr",
                "describe-repositories",
                "--repository-names",
                repo,
                "--region",
                AWS_REGION,
                "--output",
                "json",
            ],
            capture=True,
            check=False,
        )

        if result.returncode != 0:
            say(f"{repo}: not found or inaccessible. Skipping.")
            continue

        images = list_image_ids(repo)
        inventory[repo] = images

        say(f"{repo}: {len(images)} unique image manifest(s) found.")

    if not inventory:
        stop("No accessible Pharma ECR repositories were found.")

    # Dry-run mode.
    if not args.execute:
        say("DRY-RUN completed. No images were deleted.")
        say("Review the inventory before executing.")
        say("To delete images, run with --execute.")
        return

    # Require explicit confirmation.
    confirm_execution(True, "EMPTY PHARMA ECR IMAGES")

    # Delete images repository by repository.
    for repo in inventory:
        clean_repository(repo)

    # Final verification across all repositories.
    say("Performing final ECR verification...")

    for repo in inventory:
        remaining = list_image_ids(repo)

        if remaining:
            stop(
                f"FINAL VERIFICATION FAILED: "
                f"{repo} contains {len(remaining)} image(s)."
            )

        say(f"{repo}: VERIFIED EMPTY.")

    say("=" * 55)
    say("ECR IMAGE CLEANUP COMPLETED SUCCESSFULLY.")
    say("All image versions and tags have been deleted.")
    say("ECR repositories have been RETAINED.")
    say("Terraform remains responsible for deleting repositories.")
    say("=" * 55)


if __name__ == "__main__":
    main()
