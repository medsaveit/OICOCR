import os
from dotenv import load_dotenv


load_dotenv()

# ================= AUTH =================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# ================= MAIL =================
MAILBOX_EMAIL = os.getenv("MAILBOX_EMAIL")
ALLOWED_SENDER = os.getenv("ALLOWED_SENDER")
FAILURE_NOTIFY_EMAIL = os.getenv("FAILURE_NOTIFY_EMAIL")

SOURCE_FOLDER = "Inbox"
DEST_FOLDER = "Processed"

# ================= PATHS =================
ATTACHMENT_SAVE_PATH = os.getenv("ATTACHMENT_SAVE_PATH")
ATTACHMENT_SAVE_PATHAPI = os.getenv("ATTACHMENT_SAVE_PATHAPI")

# ================= GRAPH =================
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

# ================= OCR / GEMINI =================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
PROCESSED_DIR = os.getenv("PROCESSED_DIR")
FAILED_DIR = os.getenv("FAILED_DIR")

CHECK_INTERVAL = 2
RATE_LIMIT_DELAY = 10

# ================= DATABASE =================
DB_CONN_STR = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_UID')};"
    f"PWD={os.getenv('DB_PWD')}"
)