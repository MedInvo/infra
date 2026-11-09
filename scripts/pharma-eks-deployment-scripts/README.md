# Pharma Medinvo — Repeatable AWS EKS Deployment Scripts

These scripts automate the **application deployment and verification** sequence for the existing EKS cluster.

## Important safety boundary

`deploy_all.py` does **not**:
- run `terraform apply` or `terraform destroy`;
- create or modify IAM roles, EKS clusters, node groups, RDS or ECR;
- install or reinstall AWS Load Balancer Controller, External Secrets Operator or Argo CD;
- delete Kubernetes resources;
- print database Secret values.

It verifies existing prerequisites, applies the Argo CD project/Application YAMLs, requests Argo CD syncs in dependency order, and checks the application and ALB.

## Expected location

Extract this folder to:

```text
<repository-root>/infra/scripts/deployment/
```

Expected sibling layout:

```text
<repository-root>/
├── infra/
│   └── scripts/
│       └── deployment/
│           ├── common.py
│           ├── 01_connect_eks.py
│           ├── 02_verify_controllers.py
│           ├── 03_apply_argocd_apps.py
│           ├── 04_sync_shared.py
│           ├── 05_sync_backends.py
│           ├── 06_sync_frontend.py
│           ├── 07_verify_application.py
│           ├── 08_verify_ingress.py
│           └── deploy_all.py
└── gitops/
    └── argocd/
        ├── projects/pharma-project.yaml
        └── applications/
            ├── pharma-shared-dev.yaml
            ├── pharma-product-service-dev.yaml
            ├── pharma-order-service-dev.yaml
            └── pharma-frontend-dev.yaml
```

The scripts use the known project defaults:
- AWS region: `us-east-1`
- EKS cluster: `pharma-dev-cluster`
- Kubernetes namespace: `pharma-app`
- Argo CD namespace: `argocd`
- GitOps folder: `gitops`

Override defaults with environment variables if required:
- `AWS_REGION`
- `EKS_CLUSTER`
- `APP_NAMESPACE`
- `ARGO_NAMESPACE`
- `GITOPS_DIR_NAME`

## Prerequisites

Install and configure:
- AWS CLI v2
- `kubectl`
- Python 3.10+
- `curl`

The AWS identity must already have permission to describe the cluster and authenticate to it. The identity must also have the EKS Kubernetes access required by your cluster.

## Run the deployment

From the deployment folder:

```bash
python3 deploy_all.py
```

The script stops at the first failed prerequisite or deployment check. Fix that issue and rerun it; the steps are designed to be repeatable.

## Run one step independently

```bash
python3 01_connect_eks.py
python3 02_verify_controllers.py
python3 03_apply_argocd_apps.py
python3 04_sync_shared.py
python3 05_sync_backends.py
python3 06_sync_frontend.py
python3 07_verify_application.py
python3 08_verify_ingress.py
```

## Deployment order and dependencies

1. Connect to the existing EKS cluster and verify nodes.
2. Verify AWS Load Balancer Controller, External Secrets Operator and Argo CD are already Ready.
3. Apply the Argo CD project and four Application definitions.
4. Sync `pharma-shared-dev`; wait for `pharma-db-secret` ExternalSecret to become Ready and for Kubernetes Secret `postgres-secret` to contain the required keys.
5. Sync product-service, then order-service.
6. Sync frontend.
7. Verify pods, Deployments, Services and Secret metadata.
8. Verify ALB TargetGroupBinding target health and request the Ingress URL over HTTP.

## Notes / assumptions to check before first run

- `gitops/argocd/projects/pharma-project.yaml` must exist. If your project YAML is in a different path, update `03_apply_argocd_apps.py`.
- The four Application filenames and names must match the repository.
- The shared ExternalSecret must be named `pharma-db-secret`, and it must create Kubernetes Secret `postgres-secret` with keys `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
- The frontend Ingress is currently HTTP-only. `08_verify_ingress.py` tests `http://<ALB-DNS>/`. Do not enable HTTPS listener/ssl-redirect until a valid ACM certificate ARN in `us-east-1` is configured.
- The scripts expect the application Ingress and TargetGroupBinding to be in namespace `pharma-app`.
- The script waits for all Deployments in `pharma-app`; if you add unrelated Deployments there, they will also be checked.
- `kubectl apply` on Argo CD Application YAMLs updates those Application objects. It does not delete application workloads.
- These scripts do not perform Git commits or pushes. Push GitOps chart and values changes before running the deployment.

## If a step fails

The script stops and prints the failed command/check. Use the relevant diagnostics:

```bash
kubectl get nodes
kubectl get pods -A
kubectl get applications -n argocd
kubectl describe application pharma-shared-dev -n argocd
kubectl describe externalsecret pharma-db-secret -n pharma-app
kubectl describe ingress pharma-frontend -n pharma-app
kubectl get targetgroupbindings -n pharma-app
```

Never print Secret values or commit database credentials to Git.
