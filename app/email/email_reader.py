import os
import base64
from app.email.graph_client import graph_get, graph_post
from config.config import (
    ATTACHMENT_SAVE_PATHAPI, MAILBOX_EMAIL, ALLOWED_SENDER,
    SOURCE_FOLDER, DEST_FOLDER, ATTACHMENT_SAVE_PATH,
    GRAPH_BASE_URL
)
from app.db.database import insertProcessPDF

os.makedirs(ATTACHMENT_SAVE_PATH, exist_ok=True)
os.makedirs(ATTACHMENT_SAVE_PATHAPI, exist_ok=True)


def get_folder_id(headers, folder_name):
    url = f"{GRAPH_BASE_URL}/users/{MAILBOX_EMAIL}/mailFolders"
    data = graph_get(url, headers)

    for f in data.get("value", []):
        if f["displayName"].lower() == folder_name.lower():
            return f["id"]
    return None


def get_all_messages(url, headers, params):
    messages = []

    while url:
        data = graph_get(url, headers, params)
        messages.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        params = None

    return messages


def clean_filename(name: str) -> str:
    """Normalize attachment names so only one .pdf suffix remains."""
    base = name.strip()

    while base.lower().endswith(".pdf.pdf"):
        base = base[:-4]

    if base.lower().endswith(".pdf"):
        return base

    return f"{base}.pdf"


def process_emails(headers):
    source_id = get_folder_id(headers, SOURCE_FOLDER)
    dest_id = get_folder_id(headers, DEST_FOLDER)

    if not source_id or not dest_id:
        raise Exception("Source or Destination folder not found")

    base_url = (
        f"{GRAPH_BASE_URL}/users/{MAILBOX_EMAIL}"
        f"/mailFolders/{source_id}/messages"
    )

    params = {
        "$filter": f"from/emailAddress/address eq '{ALLOWED_SENDER}'",
        "$top": 10
    }

    messages = get_all_messages(base_url, headers, params)

    for msg in messages:
        msg_id = msg["id"]

        att_url = (
            f"{GRAPH_BASE_URL}/users/{MAILBOX_EMAIL}"
            f"/messages/{msg_id}/attachments"
        )

        attachments = graph_get(att_url, headers).get("value", [])

        for att in attachments:
            if (
                att["@odata.type"] == "#microsoft.graph.fileAttachment"
                and att["name"].lower().endswith(".pdf")
            ):
                file_name = clean_filename(att["name"])
                file_path = os.path.join(ATTACHMENT_SAVE_PATH, file_name)
                file_api_path = os.path.join(ATTACHMENT_SAVE_PATHAPI, file_name)

                if os.path.exists(file_path):
                    print(f"⏭️ File already exists, skipped: {file_name}")
                    continue

                pdf_bytes = base64.b64decode(att["contentBytes"])

                with open(file_path, "wb") as f:
                    f.write(pdf_bytes)

                with open(file_api_path, "wb") as f:
                    f.write(pdf_bytes)

                insertProcessPDF(file_name, "PENDING")
                print(f"✅ New file inserted: {file_name}")

        move_url = (
            f"{GRAPH_BASE_URL}/users/{MAILBOX_EMAIL}"
            f"/messages/{msg_id}/move"
        )
        graph_post(move_url, headers, {"destinationId": dest_id})

        print(f"📁 Mail moved: {msg_id}")