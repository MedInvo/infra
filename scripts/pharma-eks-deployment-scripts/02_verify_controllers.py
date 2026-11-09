from common import fail, pods_ready, say, wait_for_pods, wait_until

def main():
    say("Step 2/8: Verify existing controllers. This script does not reinstall them.")

    def alb_ready():
        return pods_ready("kube-system", "aws-load-balancer-controller")
    wait_until("AWS Load Balancer Controller pods", alb_ready, timeout_seconds=180)

    wait_for_pods("external-secrets", timeout=180)
    wait_for_pods("argocd", timeout=240)

    say("AWS Load Balancer Controller, External Secrets Operator and Argo CD pods are Ready.")

if __name__ == "__main__":
    main()
