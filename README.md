# OICOCR — Insurance Policy OCR Automation

Automated pipeline that reads insurance policy PDFs from a Microsoft 365 mailbox,
extracts structured data using Google Gemini, and saves the results into SQL Server.

## Overview

Two independent background workers run inside a single process:

1. **Email Worker** (`app/email/email_worker.py`)
   Connects to Microsoft Graph API (via MSAL app-based OAuth2), checks the mailbox
   for new attachments from allowed senders, and moves them into the local upload
   folder for processing.

2. **OCR Worker** (`app/ocr/ocr_worker.py`)
   Picks up pending files from the database (`sp_get_pending_bills`), sends each
   PDF to Google Gemini for extraction, parses the structured JSON response, and
   saves the results into SQL Server via stored procedures.

Both workers run as separate threads inside `run_workers.py`, the single entry
point for the whole system. If either worker crashes unexpectedly, it is
automatically restarted after a short delay.

## Project Structure

```
OICOCR/
├── run_workers.py            # Main entry point — starts both workers
├── requirements.txt
├── .env                       # Secrets: DB connection string, Gemini API key, etc.
├── app/
│   ├── auth/                  # MSAL OAuth2 token handling
│   ├── db/
│   │   └── database.py        # All SQL Server read/write operations
│   ├── email/
│   │   ├── email_reader.py    # Fetches attachments via Graph API
│   │   ├── email_sender.py    # Sends failure notification emails
│   │   ├── email_worker.py    # Email worker loop (start_email_worker)
│   │   └── graph_client.py    # Microsoft Graph API client
│   └── ocr/
│       ├── gemini_client.py   # (or ocr_worker.py) Gemini extraction logic
│       └── ocr_worker.py      # OCR worker loop (start_ocr_worker)
└── config/
    ├── config.py               # Loads settings from .env
    └── logger.py               # Centralized logging setup
```

## Requirements

- Python 3.10+
- SQL Server with ODBC Driver 17/18 installed
- Google Gemini API key
- Microsoft 365 app registration (Graph API, mail read permissions)

## Setup

```powershell
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

```powershell
python run_workers.py
```

Expected output:
```
Combined Worker Starting (Email + OCR)
Starting thread: EmailWorker
Starting thread: OCRWorker
Both workers are now running independently.
```

Press `Ctrl+C` to stop.

## Deployment (Windows Server)

Runs as a Windows Service using NSSM so it survives server restarts and reboots.

```powershell
# One-time setup
nssm install OICOCRWorker
#   Path:               <project>\venv\Scripts\python.exe
#   Startup directory:  <project>
#   Arguments:           run_workers.py

nssm start OICOCRWorker
```
Check status any time via `services.msc` → look for `OICOCRWorker`.

## Logs

All activity is logged via `config/logger.py` (`RotatingFileHandler`). Check the
log file for:
- Email check cycles
- OCR extraction start/success/failure per file
- Consolidated failure notifications sent

## Status Flow (policy_master table)

```
PENDING → PROCESSING → COMPLETED
                     └→ FAILED (with error message + moved to /failed folder)
```

## Notes

- Do not run two instances of this worker against the same database at the
  same time (e.g. one on production, one on UAT pointing at the same DB) —
  this can cause duplicate processing / race conditions on pending files.
- `.env` holds all secrets — never commit it to version control.