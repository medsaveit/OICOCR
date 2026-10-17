"""
Auto-insert pending policies from uploads folder into policy_master table
Run this script whenever you paste PDFs into uploads folder
"""

import os
import pyodbc
from config.config import DB_CONN_STR

UPLOADS_FOLDER = "uploads"


def get_db_connection():
    return pyodbc.connect(DB_CONN_STR)


def file_already_exists(cursor, file_name):
    """Check if file already in policy_master"""
    cursor.execute(
        "SELECT COUNT(*) FROM policy_master WHERE file_name = ?", (file_name,)
    )
    return cursor.fetchone()[0] > 0


def insert_pending_policies():
    """Scan uploads folder and insert new PDFs into policy_master"""

    if not os.path.exists(UPLOADS_FOLDER):
        print(f"❌ Folder not found: {UPLOADS_FOLDER}")
        return

    # Get all PDF files from uploads folder
    pdf_files = [f for f in os.listdir(UPLOADS_FOLDER) if f.endswith(".pdf")]

    if not pdf_files:
        print("⚠️ No PDF files found in uploads folder")
        return

    print(f"📁 Found {len(pdf_files)} PDF files in uploads folder")

    conn = get_db_connection()
    cursor = conn.cursor()

    inserted_count = 0
    skipped_count = 0

    for file_name in pdf_files:
        # Check if already exists
        if file_already_exists(cursor, file_name):
            print(f"⏭️  Skipped (already exists): {file_name}")
            skipped_count += 1
            continue

        # Insert as PENDING
        try:
            prefix_file_name = "OCR_" + file_name
            cursor.execute(
                """
                INSERT INTO policy_master (FileNames, file_name, Status, policy_no)
                VALUES (?, ?, 'PENDING', '0')
                """,
                (file_name, file_name),
            )
            conn.commit()
            print(f"✅ Inserted: {file_name}")
            inserted_count += 1
        except Exception as e:
            print(f"❌ Error inserting {file_name}: {e}")
            conn.rollback()

    cursor.close()
    conn.close()

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  ✅ Inserted: {inserted_count}")
    print(f"  ⏭️  Skipped (already exist): {skipped_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    print("🚀 Auto-inserting pending policies from uploads folder...")
    insert_pending_policies()
    print("✨ Done!")
