import argparse
from cleanup_common import (
    AWS_REGION, ECR_REPOSITORIES, NAMESPACE, ARGO_NAMESPACE,
    run, json_output, verify_aws_and_cluster, say, stop
)

def main():
    parser = argparse.ArgumentParser(description="Read-only inventory before Pharma EKS cleanup.")
    parser.parse_args()
    verify_aws_and_cluster()

    say("Argo CD Applications:")
    run(["kubectl", "get", "applications", "-n", ARGO_NAMESPACE, "-o", "wide"])
    say("Application namespace resources:")
    run(["kubectl", "get", "all,ingress,externalsecret,secret,pvc", "-n", NAMESPACE], check=False)
    say("Ingress and AWS load-balancer DNS names:")
    ing = json_output(["kubectl", "get", "ingress", "-n", NAMESPACE, "-o", "json"])
    for item in ing.get("items", []):
        name = item.get("metadata", {}).get("name", "unknown")
        hosts = item.get("status", {}).get("loadBalancer", {}).get("ingress", [])
        dns = [x.get("hostname") or x.get("ip") for x in hosts]
        say(f"Ingress/{name}: {', '.join(x for x in dns if x) or 'no address assigned'}")

    say("ECR repositories (Terraform-managed; this script will NOT delete repositories):")
    for repo in ECR_REPOSITORIES:
        result = run([
            "aws", "ecr", "describe-repositories", "--repository-names", repo,
            "--region", AWS_REGION, "--output", "json"
        ], capture=True, check=False)
        if result.returncode == 0:
            data = json_output([
                "aws", "ecr", "describe-repositories", "--repository-names", repo,
                "--region", AWS_REGION, "--output", "json"
            ])
            for r in data.get("repositories", []):
                say(f"{r.get('repositoryName')} | {r.get('repositoryUri')}")
        else:
            say(f"{repo}: not found or not accessible")

    say("Read-only inventory complete. No resources were changed.")

if __name__ == "__main__":
    main()
