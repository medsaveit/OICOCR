from app.auth.auth import get_access_token
from app.email.email_reader import process_emails


def main():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    process_emails(headers)


if __name__ == "__main__":
    main()
