import traceback
from app.email.graph_client import graph_post
from app.auth.auth import get_access_token
from config.config import GRAPH_BASE_URL, MAILBOX_EMAIL, FAILURE_NOTIFY_EMAIL


def send_consolidated_failure_notification(failed_files: list):
    """
    Sends a professional HTML email notification for failed OCR processing.

    Args:
        failed_files: List of dictionaries with keys: file_name, policy_id, reason (optional).
    """
    if not failed_files:
        return

    try:
        token = get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        count = len(failed_files)
        subject = (
            f"⚠️ OCR Alert: {count} Policy File(s) Failed Processing — Action Required"
        )

        # Generate table rows
        rows_html = ""
        for i, item in enumerate(failed_files):
            bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            reason = item.get("reason", "Not Enrolled")
            rows_html += f"""
            <tr style="background-color: {bg_color};">
                <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: center; color: #495057;">{i + 1}</td>
                <td style="padding: 12px; border: 1px solid #e0e0e0; color: #495057;">{item['file_name']}</td>
                <td style="padding: 12px; border: 1px solid #e0e0e0; color: #dc3545; font-weight: 600;">Failed</td>
                <td style="padding: 12px; border: 1px solid #e0e0e0; color: #6c757d;">{reason}</td>
            </tr>
            """

        # Professional HTML email template
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>OCR Processing Alert</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f6f9; color: #333;">
            <div style="max-width: 700px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);">

                <!-- Header -->
                <div style="background: linear-gradient(135deg, #2c3e50, #3498db); padding: 20px 24px; color: #ffffff;">
                    <h2 style="margin: 0; font-size: 20px; font-weight: 600;">🏥 MedSave — OCR Processing Alert</h2>
                    <p style="margin: 8px 0 0 0; font-size: 14px; opacity: 0.9;">Automated System Notification</p>
                </div>

                <!-- Summary Banner -->
                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 16px 24px;">
                    <p style="margin: 0; font-size: 15px; color: #856404; font-weight: 500;">
                        <strong>{count} policy file(s)</strong> failed during OCR processing. Immediate review is recommended.
                    </p>
                </div>

                <!-- Table -->
                <div style="padding: 20px 24px;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                        <thead>
                            <tr style="background-color: #2c3e50; color: #ffffff;">
                                <th style="padding: 12px; border: 1px solid #e0e0e0; text-align: left;">#</th>
                                <th style="padding: 12px; border: 1px solid #e0e0e0; text-align: left;">File Name</th>
                                <th style="padding: 12px; border: 1px solid #e0e0e0; text-align: left;">Status</th>
                                <th style="padding: 12px; border: 1px solid #e0e0e0; text-align: left;">Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>

                <!-- Footer -->
                <div style="background-color: #f8f9fa; padding: 16px 24px; border-top: 1px solid #e0e0e0; text-align: center;">
                    <p style="margin: 0; font-size: 12px; color: #6c757d;">
                        This is an automated message from the <strong>MedSave OCR System</strong>.
                        <br>Please do not reply to this email.
                        <br>© 2026 MedSave TPA. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        send_url = f"{GRAPH_BASE_URL}/users/{MAILBOX_EMAIL}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [{"emailAddress": {"address": FAILURE_NOTIFY_EMAIL}}],
            },
            "saveToSentItems": True,
        }

        graph_post(send_url, headers, payload)
        print(
            f"📧 Consolidated failure notification sent → {count} files → {FAILURE_NOTIFY_EMAIL}"
        )

    except Exception:
        print(f"⚠️ Failed to send consolidated notification:")
        print(traceback.format_exc())
