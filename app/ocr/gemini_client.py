import json
import re
import time
from google import genai
from google.genai import types
from config.config import GEMINI_API_KEY, MODEL_NAME, RATE_LIMIT_DELAY

client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------- OUTPUT SCHEMA ----------------
OCR_OUTPUT_SCHEMA = {
    "policy_no": "",
    "prev_policy_no": "",
    "insured_code": "",
    "insured_name": "",
    "issue_office_code": "",
    "issue_office_name": "",
    "product_code": "",
    "address": "",
    "address2": "",
    "pincode": "",
    "city": "",
    "state": "",
    "is_floater": 0,
    "policy_from": "",
    "policy_to": "",
    "gst_invoice_no": "",
    "gross_premium": 0,
    "number_of_persons_covered": 0,
    "plan_type": "",
    "silver_plan": "",
    "sum_insured": 0,
    "agent_broker_details": {
        "dev_off_code": "",
        "dev_off_name": "",
        "agcode": "",
        "agent_name": "",
        "Address": "",
        "Tel_Fax_Email": "",
    },
    "policy_members": [
        {
            "sr_no": 1,
            "name_of_Person": "",
            "gender": "",
            "date_of_birth": "",
            "age": 0,
            "relationship": "",
            "pre_existing_diseases": "",
            "co_pay": "",
            "sum_insured": 0,
            "cum_percentage": 0,
            "cum_bonus": 0,
        }
    ],
    "nominee_details": [
        {
            "name_of_the_nominee": "",
            "relationship_with_the_insured": "",
            "age_of_the_nominee": 0,
            "gender": "",
        }
    ],
    "optional_covers": [{"particular": "", "yes_no": "", "remark": ""}],
    "policy_history_data": [
        {
            "policy_no": "",
            "period_from": "",
            "period_to": "",
            "insurer_name": "",
            "sum_insured": 0,
        }
    ],
}


def extract_medical_bill(pdf_path):
    # -------- Upload PDF --------
    print(f"📤 Uploading PDF: {pdf_path}")
    with open(pdf_path, "rb") as f:
        uploaded_file = client.files.upload(
            file=f, config=types.UploadFileConfig(mime_type="application/pdf")
        )
    print(f"✅ Uploaded: {uploaded_file.name}")

    # -------- Rate limit delay --------
    print(f"⏳ Waiting {RATE_LIMIT_DELAY}s (rate limit)...")
    time.sleep(RATE_LIMIT_DELAY)

    # -------- Strict Prompt --------
    prompt = f"""
You are an expert insurance OCR extraction system.

TASK: Extract all insurance policy details from the attached document.

RULES:
1. Return ONLY valid JSON — no markdown, no explanation, no extra/missing keys.
2. Missing values: "" for strings, 0 for numbers, [] for lists.
3. Dates: YYYY-MM-DD. Numbers must be JSON numbers, not strings.
3a. policy_from and policy_to: Extract ONLY from the current policy's
    "Policy Period" or "Period of Insurance" section (usually shown as
    "From: DD/MM/YYYY To: DD/MM/YYYY" near the top of the schedule).
    NEVER use dates from the "Policy History" table, "Previous Policy",
    "Inception Date", or any renewal/history section for these fields.
    If the current policy period dates are not clearly visible, use "".
4. agent_broker_details is an object; policy_members, nominee_details,
   optional_covers, policy_history_data are arrays.
5. insured_name: remove any "(GSTIN: 0)" suffix.
5a. sum_insured (header/top-level): Extract the total "Sum Insured" amount shown
    at the very top of the policy schedule (usually in a separate box or line,
    e.g. "Sum Insured: 2500000"). This is the family/floater-level total
    coverage, separate from per-member amounts in the "Particulars of Persons
    Covered" table below. Extract as a number (e.g. 2500000, not "2500000 INR").
    If no such header-level sum_insured is shown, use 0.
6. product_code: copy the full policy product name from the document heading exactly
   as written (e.g. "ORIENTAL YOUTH ECO CARE POLICY - FLOATER PLAN - POLICY SCHEDULE").
7. pincode: the 6-digit code near the end of the address (after a hyphen/comma,
   e.g. "...NADIAD - 387001" → "387001"). Extract it into "pincode" and strip it
   out of "address". If none found, pincode = "".
7a. city and state: these already have their own separate fields ("city", "state").
    The "address" field must NOT repeat the city or state name at the end — strip
    them out of "address" once extracted. Example: if the printed address is
    "108, HEERA NAGAR, AJMER ROAD, JAIPUR, RAJASTHAN, 302018", then:
      city = "JAIPUR", state = "RAJASTHAN", pincode = "302018",
      address = "108, HEERA NAGAR, AJMER ROAD"
    (i.e. address keeps only the street/locality part, not city, state, or pincode).
8. is_floater: 1 if the document title/heading contains "FLOATER", else 0
   (including when it says "INDIVIDUAL").
9. sr_no: integer Sr. No. of each policy member from the members table (1, 2, 3...);
   if not shown, assign sequentially starting at 1.
9a. sum_insured (per member): extract EACH member's sum_insured strictly from
    their OWN row in the table. In floater policies:
    - Primary member (relationship = "Self") → extract their sum_insured value
      from the table (may be blank; if blank, use header "Sum Insured" value if
      shown at top of page, otherwise 0)
    - All other members (Spouse, Children, Dependents, etc.) → sum_insured = 0
      (because in floater policies, the full family coverage is represented by
      the primary member's amount; other members don't have individual amounts)
9b. CRITICAL: "Sum Insured" column is COMPLETELY DIFFERENT from "Cumulative
    Bonus" column. Never confuse them:
    - "Sum Insured" (per-member) → the coverage amount for that specific member
      (often blank in floater policies, use 0 if blank)
    - "Cumulative Bonus" → the no-claim bonus amount (e.g. 250000 rupees) — this
      is a SEPARATE field, NOT sum_insured. This goes into cum_bonus, NOT sum_insured.
    If the member's "Sum Insured" column is blank and "Cumulative Bonus" column
    has a value (e.g. 250000), the extraction must be:
      sum_insured = 0, cum_bonus = 250000
    NOT sum_insured = 250000.
10. agent_broker_details: the document has two separate "code + name" lines — keep
    them separate, do not merge:
    - "Dev.Off.Code" line → first token is dev_off_code, rest of the line is dev_off_name
    - "Agent/Broker" line → first token is agcode, rest of the line is agent_name
    These two lines are INDEPENDENT. If the "Dev.Off.Code" line is blank, missing,
    or shows only a colon with no value after it, set dev_off_code="" and
    dev_off_name="" — do NOT copy the agcode or agent_name values into these
    fields just because Dev.Off.Code looks empty. The same applies in reverse:
    never copy dev_off_code/dev_off_name into agcode/agent_name if Agent/Broker
    is blank. Each field must only ever contain data from its own line, or be
    left empty.
11. CRITICAL — Text accuracy: Every name, word, and character must be copied
    EXACTLY as printed in the document. Never substitute a name with a more
    common-sounding alternative (e.g. do not change "Sunita" to "Sujata" just
    because it seems more familiar). If any part of a word is unclear or
    unreadable, keep your best literal reading — never "auto-correct" spelling.
12. cum_percentage and cum_bonus: these refer to the "Cumulative Bonus" section
    of the policy (sometimes labelled "Cumulative Bonus %", "CB %", or
    "No Claim Bonus"), and belong to EACH individual member inside
    "policy_members" — not to the policy as a whole. If the document shows a
    single cumulative bonus % that applies to all members, repeat that same
    value in every member's cum_percentage/cum_bonus. cum_percentage is the
    bonus percentage figure (e.g. 10, 25, 50 — a plain number without "%").
    cum_bonus is the corresponding bonus amount in rupees, if shown separately.
    If either value is not present anywhere in the document, use 0.
   

JSON OUTPUT SCHEMA:
{json.dumps(OCR_OUTPUT_SCHEMA, indent=2)}

Return ONLY JSON.
"""

    # -------- Gemini Call --------
    print(f"🔄 Calling Gemini API ({MODEL_NAME})...")
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0
            ),
        )
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        raise

    print("✅ Gemini responded")

    # -------- Parse & Return --------
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"⚠️ Direct JSON parse failed: {e}")

    # Fallback: json_repair
    try:
        import json_repair

        print("🔹 Attempting JSON repair...")
        repaired = json_repair.repair_json(raw)
        result = json.loads(repaired)
        print("✅ JSON repaired successfully")
        return result
    except Exception as e:
        print(f"❌ JSON repair also failed: {e}")
        print(f"📄 Raw Response:\n{raw[:500]}")
        raise ValueError("Failed to parse JSON response from Gemini")
