# Pharma Medinvo — Safe EKS Cleanup Scripts

This package cleans up **application and selected add-on resources** while preserving all infrastructure owned by Terraform/GitHub Actions.

## Important boundary

These scripts NEVER run `terraform destroy`, `terraform apply`, or delete Terraform-managed infrastructure.

They do not delete:
- EKS cluster or node groups
- VPC, subnets, route tables, NAT gateways or security groups managed by Terraform
- RDS PostgreSQL instance, DB contents or DB subnet/security-group resources
- ECR repositories (only image manifests/tags can optionally be emptied)
- IAM roles/policies/OIDC provider
- Secrets Manager secret `pharma-medinvo/dev/app-db`
- Route 53 hosted zone/records
- S3 Terraform state bucket or lock/state objects

The ECR repositories are known from the current Terraform plan:
- `pharma-medinvo-dev-frontend`
- `pharma-medinvo-dev-order-service`
- `pharma-medinvo-dev-product-service`

## Expected location

Extract this folder to:

```text
<repository-root>/infra/scripts/cleanup/
```

It can sit beside your deployment scripts:

```text
infra/scripts/
├── deployment/
└── cleanup/
    ├── cleanup_common.py
    ├── 00_preflight.py
    ├── 01_cleanup_application.py
    ├── 02_uninstall_addons.py
    ├── 03_empty_ecr_images.py
    ├── cleanup_all.py
    └── README.md
```

Defaults:
- AWS account: `259732629629`
- Region: `us-east-1`
- EKS cluster: `pharma-dev-cluster`
- Application namespace: `pharma-app`
- Argo CD namespace: `argocd`

Override with environment variables if needed: `EXPECTED_AWS_ACCOUNT`, `AWS_REGION`, `EKS_CLUSTER`, `APP_NAMESPACE`, `ARGO_NAMESPACE`.

## Required tools

AWS CLI v2, kubectl, Helm (only for add-on removal), and Python 3.10+.

Your AWS CLI identity must be allowed to describe EKS/ECR/ELB resources and your Kubernetes identity must be allowed to manage the listed Argo CD Applications and namespace.

## Recommended order

### Step 0 — Inspect first (read-only)

```bash
cd infra/scripts/cleanup
python3 00_preflight.py
```

This prints the Argo CD Applications, app namespace resources, Ingress ALB DNS names and ECR repository names. It does not print Kubernetes Secret values.

### Step 1 — Remove application workloads and ALB

```bash
python3 01_cleanup_application.py
```

Default is dry-run. After reviewing the plan:

```bash
python3 01_cleanup_application.py --execute
```

It:
1. Verifies the AWS account, EKS cluster and current kubectl context.
2. Captures the Ingress ALB DNS name before deletion.
3. Disables automated sync for the four known Argo CD Applications.
4. Deletes the Argo CD Applications with foreground cascade so Argo CD removes tracked resources.
5. Waits for AWS Load Balancer Controller to delete the ALB after the Ingress is removed.
6. Deletes the `pharma-app` namespace, which removes remaining app resources, ExternalSecret and generated Kubernetes Secret.

**Why the ALB is not deleted directly:** the ALB was created and is owned by AWS Load Balancer Controller through the Kubernetes Ingress. Deleting the Ingress/Application is the correct owner-aware action. The script waits until AWS confirms that ALB is gone. It intentionally does not blindly delete load balancers or target groups by name.

If ALB deletion times out, stop and inspect:
```bash
kubectl get ingress -A
kubectl get targetgroupbindings -A
kubectl logs -n kube-system deployment/aws-load-balancer-controller
```
Do not continue to uninstall the ALB controller until its load balancers are gone.

### Step 2 — Optional: uninstall add-ons installed by Helm

Only do this if you intend to remove Argo CD, External Secrets Operator and AWS Load Balancer Controller as well. First inspect the exact Helm release names:

```bash
helm list -A
```

Set the exact names shown in that output. Example only — replace the release names with your actual values:

```bash
export ALB_HELM_RELEASE=aws-load-balancer-controller
export ALB_HELM_NAMESPACE=kube-system
export ESO_HELM_RELEASE=external-secrets
export ESO_HELM_NAMESPACE=external-secrets
export ARGOCD_HELM_RELEASE=argocd
export ARGOCD_HELM_NAMESPACE=argocd
```

Then preview:
```bash
python3 02_uninstall_addons.py
```

Execute only after verifying the names:
```bash
python3 02_uninstall_addons.py --execute
```

The script uninstalls in safe order: ALB controller, ESO, then Argo CD. It leaves any release unset untouched. It assumes these components were installed as Helm releases; if installed by raw manifests or another tool, use that original installation method instead.

### Step 3 — Optional: empty ECR image contents

Do this **after** application workloads are gone and before the Terraform destroy workflow tries to delete ECR repositories. ECR repositories cannot normally be deleted while they contain images unless force deletion is requested; this script empties images but does not delete repositories.

Preview:
```bash
python3 03_empty_ecr_images.py
```

Execute:
```bash
python3 03_empty_ecr_images.py --execute
```

It checks that there are no active Kubernetes pods anywhere in the cluster, deletes image manifests by digest in batches, verifies each repository is empty, and retains all three ECR repositories. It never calls `delete-repository`.

### Run the sequence

Dry-run all default steps:
```bash
python3 cleanup_all.py
```

Execute application cleanup:
```bash
python3 cleanup_all.py --execute
```

Include add-on removal and ECR image cleanup only when deliberately intended:
```bash
python3 cleanup_all.py --execute --include-addons --include-ecr-images
```

The add-on and ECR scripts have their own confirmation prompts.

## Resources that should be destroyed by the Terraform GitHub Actions workflow

After this package has completed, review your Terraform plan. Terraform should remain the single owner for:
- ECR repositories
- EKS cluster and node groups
- VPC/networking
- RDS
- IAM/OIDC
- Secrets Manager secret and related infrastructure
- Route 53 and any Terraform-managed API Gateway resources

Use your existing GitHub Actions destroy workflow and inspect its plan/artifact before approving the destroy. Never delete the Terraform S3 backend bucket/state as part of this application cleanup.

## Notes / safety

- Dry-run is the default. Nothing destructive happens without `--execute`.
- Destructive scripts ask for an exact confirmation phrase.
- The expected AWS account is checked before cleanup. If the account is different, the script stops.
- No secret values are displayed.
- The script does not directly delete ALBs, target groups, security groups or ENIs. The Kubernetes controller should clean up resources it owns after Ingress deletion.
- If Argo CD Applications are named differently in your GitOps repo, edit `APP_NAMES` in `01_cleanup_application.py` after checking `kubectl get applications -n argocd`.
- If a resource is shared with another application, inspect ownership before running the execute command.
