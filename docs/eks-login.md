Step 1: Create an EKS access entry
Run this command:



aws eks create-access-entry \
  --cluster-name pharma-dev-cluster \
  --region us-east-1 \
  --principal-arn arn:aws:iam::259732629629:user/terraform-admin \   #use your caller identity access
  --type STANDARD


This registers your IAM user as an identity that EKS can authorize. It does not, by itself, grant Kubernetes permissions.
If AWS responds that the access entry already exists, don't create it again; continue to the verification step.
Step 2: Grant Kubernetes administrator access
For your current cluster setup and ALB Controller installation, associate the EKS cluster-admin access policy with this user:

aws eks associate-access-policy \
  --cluster-name pharma-dev-cluster \
  --region us-east-1 \
  --principal-arn arn:aws:iam::259732629629:user/terraform-admin \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster


This grants broad Kubernetes administrator access. Use it for your trusted infrastructure-admin identity; for routine application access, prefer narrower permissions.
Step 3: Verify the access entry and policy


aws eks list-associated-access-policies \
  --cluster-name pharma-dev-cluster \
  --region us-east-1 \
  --principal-arn arn:aws:iam::259732629629:user/terraform-admin


Confirm that AmazonEKSClusterAdminPolicy is associated with cluster scope.
Step 4: Test your EKS connection

aws eks update-kubeconfig \
  --region us-east-1 \
  --name pharma-dev-cluster

kubectl get nodes
kubectl get pods -A


If successful, you should see your EKS worker nodes and Kubernetes pods.