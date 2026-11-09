from common import AWS_REGION, EKS_CLUSTER, check_aws_identity, check_nodes_ready, run, say

def main():
    say("Step 1/8: Verify AWS identity and connect kubectl to the existing EKS cluster.")
    check_aws_identity()
    run([
        "aws", "eks", "update-kubeconfig",
        "--region", AWS_REGION,
        "--name", EKS_CLUSTER,
    ])
    check_nodes_ready()
    say("EKS connection verified. This script does not create or modify EKS infrastructure.")

if __name__ == "__main__":
    main()
