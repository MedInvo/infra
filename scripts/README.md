es. The last four scripts are essentially the operational layer around the infrastructure Terraform created. Think of them as:
Connect → Install → Verify → Clean up

Script	Purpose	When
phase6_05_configure_eks.py	Connect your local kubectl to EKS	After terraform apply
phase6_06_install_alb_controller.py	Install AWS Load Balancer Controller	After EKS connection
phase6_07_verify_infrastructure.py	Check that AWS infrastructure is healthy	After controller installation
phase6_08_cleanup_external_resources.py	Remove resources created outside Terraform	Before terraform destroy


1. phase6_05_configure_eks.py
Simple meaning
Terraform creates the EKS cluster, but your laptop's kubectl doesn't automatically know how to communicate with that cluster.
So this script does:
Terraform
   │
   │ created EKS
   ▼
AWS EKS Cluster
   ▲
   │
   │ kubeconfig
   │
Your Laptop
   │
   ▼
kubectl

What the script does
First it gets the cluster name from Terraform:
terraform output -raw eks_cluster_name

For example:
pharma-devops-dev

Then it runs:
aws eks update-kubeconfig \
  --region us-east-1 \
  --name pharma-devops-dev

This updates your local:
~/.kube/config

Now kubectl knows:
"When the user runs kubectl, talk to this EKS cluster."

Then it checks:
kubectl config current-context
kubectl get nodes -o wide
kubectl get namespaces

Remember it as:
05 = CONNECT TO EKS

2. phase6_06_install_alb_controller.py
Now your EKS cluster exists and kubectl can communicate with it.
But Kubernetes by itself doesn't automatically create an AWS Application Load Balancer when you create an Ingress.
That's why we need:
AWS Load Balancer Controller
The flow is:
Kubernetes Ingress
       │
       ▼
AWS Load Balancer Controller
       │
       ▼
AWS ALB

What this script does
Terraform already created the IAM role for the controller:
Terraform
   │
   └── IAM Role
          │
          ▼
AWS Load Balancer Controller

The script then:
Step 1 — Add Helm repository
helm repo add eks https://aws.github.io/eks-charts

Helm is basically the package manager we use to install Kubernetes applications.
Step 2 — Create ServiceAccount
Kubernetes
└── kube-system
    └── aws-load-balancer-controller

The ServiceAccount is associated with the IAM role created by Terraform.
This is the important relationship:
Kubernetes ServiceAccount
          │
          │ IRSA
          ▼
AWS IAM Role
          │
          ▼
AWS APIs

Step 3 — Install controller using Helm
Conceptually:
helm upgrade --install \
  aws-load-balancer-controller \
  eks/aws-load-balancer-controller

Then the script waits for:
deployment/aws-load-balancer-controller

to become ready.
Remember it as:
06 = INSTALL THE AWS LOAD BALANCER BRAIN

The controller is the "brain" that watches Kubernetes resources and creates/manages AWS load balancers.
3. phase6_07_verify_infrastructure.py
Now we've:
Terraform
   ↓
AWS infrastructure
   ↓
EKS
   ↓
ALB Controller

Before moving to application deployment, we need to make sure everything is actually working.
That's what Phase 6.07 does.
It is primarily a read-only health check.
It checks things such as:
AWS identity
aws sts get-caller-identity

So we know which AWS account/user/role we're operating with.
Terraform outputs
For example:
VPC
ECR
EKS
RDS
IAM

EKS
aws eks list-clusters
kubectl get nodes
kubectl get namespaces

ECR
Checks that our repositories exist:
frontend
product-service
order-service

RDS
Checks that PostgreSQL exists.
ALB Controller
Checks:
kubectl get deployment
kubectl get pods

Load Balancers / Ingress
It also checks whether an ALB exists.
But remember:
At this point we may not have an ALB yet.

Why?
Because the ALB is created when our application has a Kubernetes Ingress.
Later:
Argo CD
   ↓
Application manifests
   ↓
Ingress
   ↓
AWS Load Balancer Controller
   ↓
ALB

So no ALB at this stage can be completely normal.
Remember it as:
07 = CHECK EVERYTHING

4. phase6_08_cleanup_external_resources.py
This one is completely different.
We don't run it after deployment.
We run it when we're finished and want to destroy the infrastructure.
Why do we need it?
Because Terraform did not create everything.
For example:
Terraform creates:
├── VPC
├── EKS
├── RDS
├── ECR
├── IAM
└── ALB Controller IAM resources

Kubernetes/Helm creates:
├── Ingress
├── ALB
├── Target Groups
├── Listeners
└── Controller Kubernetes resources

Terraform doesn't own the ALB created dynamically by the Kubernetes controller.
Therefore we need:
Delete Ingress
      ↓
AWS Load Balancer Controller
      ↓
Delete ALB
      ↓
Wait until ALB is gone
      ↓
Uninstall Controller
      ↓
Terraform destroy

Why delete Ingress first?
Because the controller created the ALB because of the Ingress.
So:
Ingress exists
     ↓
Controller sees Ingress
     ↓
ALB exists

Delete:
Ingress

and the controller should remove:
ALB
Target Group
Listener

Then we uninstall the controller.
Very important
The script does not manually delete the ALB.
That's intentional.
We want the owner of the ALB—the AWS Load Balancer Controller—to clean it up correctly.
Remember it as:
08 = CLEAN WHAT TERRAFORM DOESN'T OWN

The whole Phase 6 picture
This is the easiest way to remember all four:
                TERRAFORM APPLY
                      │
                      ▼
              AWS Infrastructure
                      │
                      ▼
          ┌───────────────────────┐
          │ 05 Configure EKS      │
          │                       │
          │ Laptop → EKS          │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ 06 Install ALB       │
          │    Controller         │
          │                       │
          │ Helm + IRSA           │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ 07 Verify             │
          │                       │
          │ Check AWS + EKS       │
          │ + RDS + ECR + ALB     │
          └───────────┬───────────┘
                      │
                      ▼
             Deploy Application
                 with Argo CD
                      │
                      ▼
                   TESTING
                      │
                      ▼
                FINISHED?
                      │
                      ▼
          ┌───────────────────────┐
          │ 08 Cleanup             │
          │                       │
          │ Ingress → ALB →       │
          │ Controller cleanup    │
          └───────────┬───────────┘
                      │
                      ▼
             terraform destroy

One-line memory trick
05 → Connect
06 → Install
07 → Verify
08 → Cleanup
So after terraform apply, your immediate sequence is:
python3 scripts/phase6_05_configure_eks.py

then:
python3 scripts/phase6_06_install_alb_controller.py

then:
python3 scripts/phase6_07_verify_infrastructure.py

And much later, when destroying:
python3 scripts/phase6_08_cleanup_external_resources.py