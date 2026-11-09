from common import NAMESPACE, sync_application, wait_for_deployments, say

def main():
    say("Step 5/8: Sync backend microservices.")
    # Product first, then order. Order-service consumes product-service and postgres.
    sync_application("pharma-product-service-dev")
    sync_application("pharma-order-service-dev")
    wait_for_deployments(NAMESPACE)
    say("Backend Deployments completed their rollout.")

if __name__ == "__main__":
    main()
