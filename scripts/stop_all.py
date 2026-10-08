import subprocess


NAMESPACE = "pharma-app"
CLUSTER = "pharma-cluster"


def run(command):
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command)


def contexts_except_default():
    result = subprocess.run(
        ["kubectl", "config", "get-contexts", "-o", "name"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [context for context in result.stdout.splitlines() if context != "default"]


print("======================================")
print(" Stopping Pharma DevOps Environment")
print("======================================")


# Kubernetes namespace
print("\n[1/3] Deleting Kubernetes namespace...")
run([
    "kubectl",
    "delete",
    "namespace",
    NAMESPACE,
    "--ignore-not-found=true"
])


# Kind cluster
print("\n[2/3] Deleting kind cluster...")
run([
    "kind",
    "delete",
    "cluster",
    "--name",
    CLUSTER
])


# Kubernetes contexts
print("\n[3/3] Removing Kubernetes contexts except 'default'...")
for context in contexts_except_default():
    run(["kubectl", "config", "delete-context", context])


print("\n======================================")
print(" Environment stopped successfully")
print("======================================")
