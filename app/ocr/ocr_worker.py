import os
import time
import shutil
import traceback
import threading

from google.genai.errors import ServerError

from config.config import UPLOAD_DIR, PROCESSED_DIR, FAILED_DIR, CHECK_INTERVAL
from config.logger import get_logger

from app.db.database import (
    get_pending_bills,
    mark_completed,
    mark_failed,
    save_to_database,
    is_file_already_processed,
    insertProcessPDF,
    get_policy_statuses,
)

from app.ocr.gemini_client import extract_medical_bill
from app.email.email_sender import send_consolidated_failure_notification

log = get_logger("ocr_worker")

OCR_TIMEOUT_SECONDS = 180

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FAILED_DIR, exist_ok=True)


def safe_move(src, dest_dir, filename):
    try:
        if os.path.exists(src):
            dest_path = os.path.join(dest_dir, filename)
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(src, dest_path)
    except Exception:
        log.warning(f"safe_move failed for {filename}:\n{traceback.format_exc()}")


def process_single_bill(policy_id, file_name, pdf_path, result_holder):
    try:
        log.info(f"Thread started for: {file_name}")
        data = extract_medical_bill(pdf_path)
        log.info(f"OCR extraction completed: {file_name}")
        result_holder["data"] = data
        log.info(f"Result stored successfully: {file_name}")
    except Exception as e:
        log.error(f"Thread error for {file_name}: {e}")
        result_holder["error"] = traceback.format_exc()


def start_ocr_worker(run_once=False):
    log.info("OCR Worker started (timeout mode)...")
    run_policy_ids = set()
    run_total_count = 0
    run_completed_count = 0
    run_failed_count = 0
    run_skipped_count = 0

    while True:
        try:
            bills = get_pending_bills()

            if not bills:
                if run_once:
                    statuses = get_policy_statuses(run_policy_ids)
                    status_counts = {
                        "COMPLETED": sum(
                            status == "COMPLETED" for status in statuses.values()
                        ),
                        "FAILED": sum(
                            status == "FAILED" for status in statuses.values()
                        ),
                        "PENDING": sum(
                            status in {"PENDING", "PROCESSING"}
                            for status in statuses.values()
                        ),
                    }
                    log.info(
                        "OCR run finished: fetched=%d, completed=%d, failed=%d, "
                        "skipped=%d | database: completed=%d, failed=%d, pending=%d",
                        run_total_count,
                        run_completed_count,
                        run_failed_count,
                        run_skipped_count,
                        status_counts["COMPLETED"],
                        status_counts["FAILED"],
                        status_counts["PENDING"],
                    )
                    log.info("OCR batch completed. Worker stopped.")
                    return
                time.sleep(CHECK_INTERVAL)
                continue

            total_count = len(bills)
            completed_count = 0
            failed_count = 0
            skipped_count = 0
            failed_files = []

            run_total_count += total_count

            log.info(f"OCR batch started: {total_count} pending policy(s)")

            for policy_id, file_name in bills:
                run_policy_ids.add(policy_id)
                pdf_path = os.path.join(UPLOAD_DIR, file_name)
                log.info(f"Looking for PDF: {pdf_path}")
                log.info(f"File exists: {os.path.exists(pdf_path)}")

                # Skip if already completed
                check = is_file_already_processed(file_name)
                if check["exists"] and check["status"] == "COMPLETED":
                    log.warning(
                        f"Duplicate detected — already completed: {file_name} (Policy ID: {check['policy_id']})"
                    )
                    safe_move(pdf_path, PROCESSED_DIR, file_name)
                    skipped_count += 1
                    run_skipped_count += 1
                    log.info(
                        f"Progress: {completed_count + failed_count + skipped_count}/{total_count} "
                        f"| completed={completed_count}, failed={failed_count}, skipped={skipped_count}"
                    )
                    continue

                # Failure point 1 — File missing
                if not os.path.exists(pdf_path):
                    err = "File not found in uploads folder"
                    log.error(f"File not found: {file_name}")
                    mark_failed(policy_id, err)
                    failed_files.append(
                        {"file_name": file_name, "policy_id": policy_id}
                    )
                    failed_count += 1
                    run_failed_count += 1
                    log.info(
                        f"Progress: {completed_count + failed_count + skipped_count}/{total_count} "
                        f"| completed={completed_count}, failed={failed_count}, skipped={skipped_count}"
                    )
                    continue

                log.info(f"Processing: {file_name} (timeout: {OCR_TIMEOUT_SECONDS}s)")

                result_holder = {"data": None, "error": None}

                thread = threading.Thread(
                    target=process_single_bill,
                    args=(policy_id, file_name, pdf_path, result_holder),
                    daemon=True,
                )
                thread.start()
                thread.join(timeout=OCR_TIMEOUT_SECONDS)

                # Failure point 2 — Timeout
                if thread.is_alive():
                    err = f"OCR timed out after {OCR_TIMEOUT_SECONDS} seconds"
                    log.error(f"OCR timeout: {file_name} | Policy ID: {policy_id}")
                    mark_failed(policy_id, err)
                    safe_move(pdf_path, FAILED_DIR, file_name)
                    failed_files.append(
                        {"file_name": file_name, "policy_id": policy_id}
                    )
                    failed_count += 1
                    run_failed_count += 1
                    log.info(
                        f"Progress: {completed_count + failed_count + skipped_count}/{total_count} "
                        f"| completed={completed_count}, failed={failed_count}, skipped={skipped_count}"
                    )
                    continue

                # Failure point 3 — OCR exception
                if result_holder["error"]:
                    err = result_holder["error"]
                    log.error(f"OCR failed for {file_name}:\n{err}")
                    mark_failed(policy_id, err)
                    safe_move(pdf_path, FAILED_DIR, file_name)
                    failed_files.append(
                        {"file_name": file_name, "policy_id": policy_id}
                    )
                    failed_count += 1
                    run_failed_count += 1
                    log.info(
                        f"Progress: {completed_count + failed_count + skipped_count}/{total_count} "
                        f"| completed={completed_count}, failed={failed_count}, skipped={skipped_count}"
                    )
                    continue

                # OCR succeeded — save to database
                try:
                    save_to_database(policy_id, result_holder["data"])
                    safe_move(pdf_path, PROCESSED_DIR, file_name)
                    mark_completed(policy_id)
                    log.info(f"Successfully completed: {file_name}")
                    completed_count += 1
                    run_completed_count += 1
                except Exception:
                    err = str(traceback.format_exc())[:500]
                    log.error(f"Database save failed for {file_name}:\n{err}")
                    try:
                        mark_failed(policy_id, err)
                    except Exception:
                        log.error(f"mark_failed also failed:\n{traceback.format_exc()}")
                    safe_move(pdf_path, FAILED_DIR, file_name)
                    failed_files.append(
                        {"file_name": file_name, "policy_id": policy_id}
                    )
                    failed_count += 1
                    run_failed_count += 1
                    log.info(f"Moved to failed directory: {file_name}")

                log.info(
                    f"Progress: {completed_count + failed_count + skipped_count}/{total_count} "
                    f"| completed={completed_count}, failed={failed_count}, skipped={skipped_count}"
                )

            # Send consolidated failure notification
            if failed_files:
                log.warning(
                    f"Sending consolidated failure notification for {len(failed_files)} failed file(s)"
                )
                send_consolidated_failure_notification(failed_files)

            log.info(
                f"OCR batch finished: total={total_count}, completed={completed_count}, "
                f"failed={failed_count}, skipped={skipped_count}"
            )

            time.sleep(CHECK_INTERVAL)

        except Exception:
            log.critical(f"Worker crash prevented:\n{traceback.format_exc()}")
            time.sleep(5)
