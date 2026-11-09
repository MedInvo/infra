from common import NAMESPACE, ARGO_NAMESPACE, run, say, verify_database_secret, wait_for_deployments

def main():
    say("Step 7/8: Verify application resources and Argo CD status.")
    run(["kubectl", "get", "applications", "-n", ARGO_NAMESPACE])
    run(["kubectl", "get", "pods", "-n", NAMESPACE, "-o", "wide"])
    run(["kubectl", "get", "services", "-n", NAMESPACE])
    run(["kubectl", "get", "externalsecrets", "-n", NAMESPACE])
    run(["kubectl", "get", "secret", "postgres-secret", "-n", NAMESPACE])
    verify_database_secret()
    wait_for_deployments(NAMESPACE)
    say("Application resources verified.")

if __name__ == "__main__":
    main()
