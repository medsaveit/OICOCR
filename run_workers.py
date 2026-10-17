import threading
import time
import traceback
from functools import partial

from config.logger import get_logger
from app.ocr.ocr_worker import start_ocr_worker
from email_worker import start_email_worker

log = get_logger("combined_worker")


def run_thread_forever(target_func, name):
    """
    Wraps a worker function so that if it ever crashes completely
    (should not normally happen since each worker has its own try/except loop),
    it restarts instead of silently dying.
    """
    while True:
        try:
            log.info(f"Starting thread: {name}")
            target_func()
        except Exception:
            log.critical(f"{name} crashed unexpectedly:\n{traceback.format_exc()}")
            log.info(f"Restarting {name} in 10 seconds...")
            time.sleep(10)


def main():
    log.info("=" * 50)
    log.info("Combined Worker Starting (Email + OCR)")
    log.info("=" * 50)

    email_thread = threading.Thread(
        target=run_thread_forever, args=(start_email_worker, "EmailWorker"), daemon=True
    )

    ocr_thread = threading.Thread(
        target=run_thread_forever,
        args=(partial(start_ocr_worker, run_once=False), "OCRWorker"),
        daemon=True,
    )

    email_thread.start()
    ocr_thread.start()

    log.info("Both workers are now running independently.")

    try:
        while True:
            time.sleep(60)
            if not email_thread.is_alive():
                log.critical("EmailWorker thread is dead!")
            if not ocr_thread.is_alive():
                log.critical("OCRWorker thread is dead!")
    except KeyboardInterrupt:
        log.info("Shutdown signal received. Exiting.")


if __name__ == "__main__":
    main()

    # Multithreading allows the email worker and OCR worker to run concurrently in the same process,
    # enabling efficient handling of tasks without blocking each other.
    # Each worker has its own loop and error handling, ensuring that if one worker crashes,
    # it can be restarted without affecting the other. The main thread monitors the health of both workers
    # and logs any unexpected crashes, providing a robust and resilient system for processing emails
    # and performing OCR tasks.
