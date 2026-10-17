import json
import pyodbc
import re
from config.config import DB_CONN_STR

DB_CONN_STR_WITH_TIMEOUT = DB_CONN_STR


def safe_str(val, max_len=500):
    """Convert value to string and truncate to max length"""
    return str(val or "")[:max_len]


def get_pending_bills():
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute("EXEC sp_get_pending_bills")
        return cursor.fetchall()


def get_policy_statuses(policy_ids):
    """Return the current database status for the supplied policy IDs."""
    if not policy_ids:
        return {}

    placeholders = ",".join("?" for _ in policy_ids)
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT policy_id, Status FROM policy_master "
            f"WHERE policy_id IN ({placeholders})",
            tuple(policy_ids),
        )
        return {row[0]: str(row[1]).upper() for row in cursor.fetchall()}


def insertProcessPDF(file_name, status):
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO policy_master (FileNames, file_name, Status, policy_no)
            VALUES (?, ?, ?, ?)
            """,
            (file_name, file_name, status, "0"),
        )
        conn.commit()


def mark_processing(policy_id):
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE policy_master
            SET Status = 'PROCESSING'
            WHERE policy_id = ? AND Status = 'PENDING'
            """,
            (policy_id,),
        )
        conn.commit()


def mark_completed(policy_id):
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE policy_master
            SET Status = 'COMPLETED'
            WHERE policy_id = ?
            """,
            (policy_id,),
        )
        conn.commit()


def clean_indian_amount(val):
    """Convert Indian format amount string to integer"""
    if not val:
        return 0
    cleaned = str(val).replace(",", "").strip()
    try:
        return int(float(cleaned))
    except (TypeError, ValueError):
        return 0


def mark_failed(policy_id, error_msg=None):
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute(
            "EXEC sp_mark_policy_failed ?, ?", (policy_id, safe_str(error_msg, 500))
        )
        conn.commit()


def is_file_already_processed(file_name):
    """Check if file already exists in DB with non-failed status"""
    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT policy_id, Status FROM policy_master
            WHERE file_name = ?
            AND Status = 'COMPLETED'
            """,
            (file_name,),
        )
        row = cursor.fetchone()
        if row:
            return {"exists": True, "policy_id": row[0], "status": row[1]}
        return {"exists": False}


def save_to_database(policy_id, data):
    json_string = json.dumps(data, ensure_ascii=False)
    policy_no = safe_str(data.get("policy_no"), 50)

    with pyodbc.connect(DB_CONN_STR_WITH_TIMEOUT) as conn:
        conn.timeout = 30
        cursor = conn.cursor()
        try:
            # ---------------- POLICY MASTER ----------------
            cursor.execute(
                "EXEC sp_update_policy_master ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?",
                (
                    policy_id,
                    safe_str(data.get("policy_no"), 50),
                    safe_str(data.get("prev_policy_no"), 100),
                    safe_str(data.get("insured_code"), 100),
                    safe_str(data.get("insured_name"), 500),
                    safe_str(data.get("issue_office_code"), 100),
                    safe_str(data.get("issue_office_name"), 200),
                    safe_str(data.get("address"), 1000),
                    safe_str(data.get("policy_from"), 500),
                    safe_str(data.get("policy_to"), 500),
                    safe_str(data.get("gst_invoice_no"), 200),
                    clean_indian_amount(data.get("gross_premium")),
                    json_string,
                    clean_indian_amount(data.get("sum_insured")),
                    safe_str(data.get("state"), 500),
                    safe_str(data.get("city"), 500),
                    safe_str(data.get("plan_type"), 500),
                    safe_str(data.get("product_code"), 500),
                    safe_str(data.get("pincode"), 10),
                    1 if data.get("is_floater") == 1 else 0,
                    safe_str(data.get("product_code"), 200),
                ),
            )

            # ---------------- AGENT / BROKER ----------------
            agent = data.get("agent_broker_details")
            if agent and isinstance(agent, dict):
                # Safety check: Gemini sometimes copies the Agent/Broker code
                # into dev_off_code when the Dev.Off.Code line is actually blank
                # in the PDF. If both codes match, treat dev_off_code as empty.
                dev_code = (agent.get("dev_off_code") or "").strip()
                ag_code = (agent.get("agcode") or "").strip()
                if dev_code and ag_code and dev_code == ag_code:
                    agent["dev_off_code"] = ""
                    agent["dev_off_name"] = ""

                # Split Tel_Fax_Email into phone and email
                raw_contact = agent.get("Tel_Fax_Email", "") or ""
                email = ""
                phone_parts = []
                for part in re.split(r"[//,;|]+", raw_contact):
                    part = part.strip()
                    if "@" in part:
                        email = part
                    elif part:
                        phone_parts.append(part)
                phone = ", ".join(phone_parts)

                cursor.execute(
                    "EXEC sp_insert_policy_agent_broker ?,?,?,?,?,?,?,?,?",
                    (
                        policy_id,
                        safe_str(policy_no, 50),
                        safe_str(agent.get("dev_off_code"), 100),
                        safe_str(
                            agent.get("dev_off_name"), 200
                        ),  # -> agent_broker column
                        safe_str(agent.get("agent_name"), 200),  # -> agent_name column
                        safe_str(agent.get("Address"), 1000),
                        safe_str(phone, 500),
                        safe_str(agent.get("agcode"), 100),  # -> AGCODE column
                        safe_str(email, 200),
                    ),
                )

            # ---------------- POLICY MEMBERS ----------------
            members = data.get("policy_members", [])

            # Safety net: in floater policies, only the primary member (Self)
            # should have a sum_insured value. All other members (Spouse, Children,
            # Dependents) should have sum_insured = 0, since the family is covered
            # under a single floater sum insured amount tied to the primary member.
            # Also: if the per-member Sum Insured column in the table is blank,
            # use the header-level sum_insured (top of page) for the primary member.
            if data.get("is_floater") == 1 and members:
                header_sum_insured = data.get("sum_insured")  # from top of PDF

                for m in members:
                    is_primary = (
                        str(m.get("relationship", "")).strip().lower() == "self"
                    )

                    if is_primary:
                        # Primary member: if their sum_insured is blank/null, use header value
                        member_sum = m.get("sum_insured")
                        if member_sum in (None, 0, "0", "", "NULL"):
                            if header_sum_insured not in (None, 0, "0", ""):
                                m["sum_insured"] = header_sum_insured
                            else:
                                m["sum_insured"] = 0
                    else:
                        # Non-primary member in floater → sum_insured must be 0
                        m["sum_insured"] = 0

            for item in members:
                cursor.execute(
                    "EXEC sp_insert_policy_members ?,?,?,?,?,?,?,?,?,?,?,?,?",
                    (
                        policy_id,
                        safe_str(policy_no, 50),
                        int(item.get("sr_no") or 0),
                        safe_str(item.get("name_of_Person"), 200),
                        safe_str(item.get("gender"), 10),
                        safe_str(item.get("date_of_birth"), 50),
                        safe_str(item.get("age") or 0, 50),
                        safe_str(item.get("relationship"), 50),
                        clean_indian_amount(item.get("sum_insured")),
                        safe_str(item.get("pre_existing_diseases"), 500),
                        safe_str(item.get("co_pay"), 500),
                        safe_str(item.get("cum_percentage"), 50),
                        clean_indian_amount(item.get("cum_bonus")),
                    ),
                )

            # ---------------- NOMINEE DETAILS ----------------
            for item in data.get("nominee_details", []):
                cursor.execute(
                    "EXEC sp_insert_policy_nominee ?,?,?,?,?,?",
                    (
                        policy_id,
                        safe_str(policy_no, 50),
                        safe_str(item.get("name_of_the_nominee"), 200),
                        safe_str(item.get("relationship_with_the_insured"), 100),
                        safe_str(item.get("age_of_the_nominee"), 50),
                        safe_str(item.get("gender"), 10),
                    ),
                )

            # ---------------- OPTIONAL COVERS ----------------
            for cover in data.get("optional_covers", []):
                cursor.execute(
                    "EXEC sp_insert_policy_optional_covers ?,?,?,?,?",
                    (
                        policy_id,
                        safe_str(policy_no, 50),
                        safe_str(cover.get("particular"), 500),
                        safe_str(cover.get("yes_no"), 10),
                        safe_str(cover.get("remark"), 500),
                    ),
                )

            # ---------------- POLICY HISTORY ----------------
            for history in data.get("policy_history_data", []):
                cursor.execute(
                    "EXEC sp_insert_policy_history ?,?,?,?,?,?",
                    (
                        policy_id,
                        safe_str(history.get("policy_no"), 50),
                        safe_str(history.get("period_from"), 20),
                        safe_str(history.get("period_to"), 20),
                        safe_str(history.get("insurer_name"), 200),
                        clean_indian_amount(history.get("sum_insured")),
                    ),
                )

            conn.commit()
            print(f"✅ Policy {policy_id} (Policy No: {policy_no}) saved successfully")

        except Exception as e:
            conn.rollback()
            print(f"❌ Error saving policy {policy_id} (Policy No: {policy_no}): {e}")
            raise
