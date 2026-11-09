from common import NAMESPACE, sync_application, wait_for_deployments, say

def main():
    say("Step 6/8: Sync frontend application.")
    sync_application("pharma-frontend-dev")
    wait_for_deployments(NAMESPACE)
    say("Frontend and application Deployments are rolled out.")

if __name__ == "__main__":
    main()
