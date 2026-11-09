from common import NAMESPACE, sync_application, verify_database_secret, say

def main():
    say("Step 4/8: Sync shared configuration and wait for the database Secret.")
    sync_application("pharma-shared-dev")
    verify_database_secret()
    say("Shared configuration and database Secret are ready.")

if __name__ == "__main__":
    main()
