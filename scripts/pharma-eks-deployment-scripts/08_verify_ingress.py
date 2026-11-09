from common import say, verify_target_groups, verify_ingress_http, run, NAMESPACE

def main():
    say("Step 8/8: Verify ALB targets and test the frontend over HTTP.")
    run(["kubectl", "get", "ingress", "-n", NAMESPACE])
    verify_target_groups(timeout=240)
    verify_ingress_http(timeout=240)
    say("ALB target health and frontend HTTP response verified.")
    say("This project currently uses HTTP-only ingress. HTTPS requires a valid ACM certificate ARN.")

if __name__ == "__main__":
    main()
