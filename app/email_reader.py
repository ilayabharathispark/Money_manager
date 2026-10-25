"""
email_reader.py — Gmail API integration to fetch bank alert emails.

First run: Opens a browser for Google OAuth consent.
Saves credentials to data/gmail_token.json for future use.

Setup steps:
1. Go to https://console.cloud.google.com/
2. Create a project → Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download as credentials.json and place in project root
"""

import os
import sys
import base64
import email as email_lib
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Gmail read-only scope is all we need
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "data" / "gmail_token.json"


import threading

_thread_local = threading.local()
_creds_cache = None


def get_credentials():
    """Load or refresh Gmail OAuth credentials."""
    global _creds_cache
    if _creds_cache and _creds_cache.valid:
        return _creds_cache

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "❌ credentials.json not found!\n"
                    "Please download it from Google Cloud Console:\n"
                    "  1. Go to https://console.cloud.google.com/\n"
                    "  2. APIs & Services → Credentials\n"
                    "  3. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "  4. Download JSON → rename to credentials.json → place in project root"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.parent.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
        print(f"✅ Gmail token saved to {TOKEN_FILE}")

    _creds_cache = creds
    return creds


def get_gmail_service():
    """
    Return a thread-local Gmail service instance.
    Ensures safe concurrent calls in ThreadPoolExecutor without SSL socket collisions.
    """
    if not hasattr(_thread_local, "service") or _thread_local.service is None:
        creds = get_credentials()
        _thread_local.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _thread_local.service


import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_bank_emails(start_date: str = None, end_date: str = None, already_synced_ids: set = None, max_workers: int = 3) -> list[dict]:
    """
    Fetch emails from the bank sender address within a date range.
    Uses bounded concurrency (default 3 workers) with automatic retry and backoff.
    already_synced_ids: set of msg_ids already in DB — skips content fetch for these.
    Returns list of dicts: {msg_id, subject, body, date} for NEW emails only.
    """
    sender = os.getenv("BANK_EMAIL_SENDER", "alerts@abc.bank.com")
    already_synced_ids = already_synced_ids or set()

    service = get_gmail_service()

    # Build Gmail search query with date range
    query = f"from:{sender}"
    if start_date:
        query += f" after:{start_date.replace('-', '/')}"
    if end_date:
        query += f" before:{end_date.replace('-', '/')}"

    print(f"📬 Fetching email IDs from: {sender}")
    if start_date or end_date:
        print(f"   Date range: {start_date or 'beginning'} → {end_date or 'today'}")

    # Step 1: Fetch only IDs (very fast — no content downloaded)
    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=500,
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        print("📭 No emails found from bank sender.")
        return []

    all_ids = [m["id"] for m in messages]
    new_ids = [mid for mid in all_ids if mid not in already_synced_ids]

    print(f"📨 Found {len(all_ids)} emails | {len(all_ids) - len(new_ids)} already synced | {len(new_ids)} new to fetch")

    if not new_ids:
        print("✅ All emails already in database. Nothing to fetch.")
        return []

    # Step 2: Fetch full content with 3 workers and exponential retry backoff
    print(f"⚡ Downloading {len(new_ids)} emails using {max_workers} parallel workers...")
    emails = []

    def _download_single(msg_id):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                svc = get_gmail_service()
                msg = svc.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
                return {
                    "msg_id":  msg_id,
                    "subject": _get_header(msg, "Subject"),
                    "date":    _get_header(msg, "Date"),
                    "body":    _extract_body(msg),
                }
            except Exception as e:
                if attempt < max_retries:
                    wait_time = 1.0 * (2 ** (attempt - 1))
                    time.sleep(wait_time)
                else:
                    print(f"⚠️  Could not fetch message {msg_id} after {max_retries} attempts: {e}")
                    return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_download_single, mid): mid for mid in new_ids}
        for future in as_completed(futures):
            res = future.result()
            if res:
                emails.append(res)

    print(f"✅ Downloaded {len(emails)} new emails concurrently.")
    return emails


def _get_header(msg: dict, name: str) -> str:
    """Extract a specific header value from a Gmail message."""
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(msg: dict) -> str:
    """
    Extract plain text body from a Gmail message.
    Handles simple messages and multipart messages.
    """
    payload = msg.get("payload", {})

    # Simple (non-multipart) message
    if "body" in payload and payload["body"].get("data"):
        return _decode_base64(payload["body"]["data"])

    # Multipart message — find the text/plain part
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return _decode_base64(data)

    # Fallback: try snippet
    return msg.get("snippet", "")


def _decode_base64(data: str) -> str:
    """Decode Gmail's URL-safe base64 encoded text."""
    try:
        decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return decoded
    except Exception:
        return ""


if __name__ == "__main__":
    emails = fetch_bank_emails(max_results=5)
    for e in emails:
        print(f"\n--- {e['subject']} ---")
        print(e["body"][:300])
