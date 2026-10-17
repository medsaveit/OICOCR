"""
enroll_all.py
Run this AFTER ocr_main.py completes.
Calls usp_enrollmentOICSoftdata SP for all COMPLETED policies.
"""

import pyodbc
from config.config import DB_CONN_STR
from config.logger import get_logger

log = get_logger("enroll_all")


def get_completed_policies():
    """Get today's COMPLETED policies that are not yet enrolled."""
    with pyodbc.connect(DB_CONN_STR) as conn:
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("""
            SELECT policy_id, policy_no, file_name
            FROM policy_master
            WHERE Status = 'COMPLETED'
              AND (is_enrolled IS NULL OR is_enrolled = 0)
              AND created_at >= CAST(GETDATE() AS date)
              AND created_at < DATEADD(day, 1, CAST(GETDATE() AS date))
            ORDER BY policy_id ASC
            """)
        return cursor.fetchall()


def enroll_all_policies():
    """Call the enrollment SP once for all matching PDF policies."""
    with pyodbc.connect(DB_CONN_STR) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "EXEC [dbo].[usp_enrollmentOICSoftdata] @Fcby='AI', @ipaddress='SYS', @FileName='*.pdf'"
        )
        while cursor.nextset():
            pass
        conn.commit()


def count_enrolled_policies(policy_numbers):
    """Count requested policies that actually reached the enrollment table."""
    if not policy_numbers:
        return 0

    placeholders = ",".join("?" for _ in policy_numbers)
    with pyodbc.connect(DB_CONN_STR) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM dbo.mimspol1000 WHERE polno IN ({placeholders})",
            tuple(policy_numbers),
        )
        return cursor.fetchone()[0]


def enroll_all():
    print("🚀 Starting enrollment for today's completed policies...")

    policies = get_completed_policies()

    if not policies:
        print("⚠️ No completed policies found for enrollment.")
        return

    print(f"📋 Found {len(policies)} today's completed policy(s) to enroll")

    try:
        enroll_all_policies()
        policy_numbers = [policy_no for _, policy_no, _ in policies]
        enrolled_count = count_enrolled_policies(policy_numbers)
        if enrolled_count == len(policies):
            print(f"✅ Enrollment verified for {enrolled_count} policy(s)")
        else:
            print(
                "⚠️ Enrollment SP executed, but target-table verification found "
                f"{enrolled_count}/{len(policies)} policy(s)."
            )
            print(
                "   The SP returned without a Python exception, but did not "
                "insert every requested policy."
            )
    except Exception as e:
        print(f"❌ Enrollment SP failed: {e}")


if __name__ == "__main__":
    enroll_all()
