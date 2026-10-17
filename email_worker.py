import time
import traceback
from app.auth.auth import get_access_token
from app.email.email_reader import process_emails

CHECK_INTERVAL = 300


def start_email_worker():
    print("✅ Email Worker Started...")
    while True:
        try:
            print("📧 Checking emails...")
            token = get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            process_emails(headers)
            print(f"✅ Done. Next check in {CHECK_INTERVAL // 60} minutes...")
            time.sleep(CHECK_INTERVAL)
        except Exception:
            print("🔥 Email Worker Error:")
            print(traceback.format_exc())
            print("⏳ Retrying in 60 seconds...")
            time.sleep(60)


if __name__ == "__main__":
    start_email_worker()
