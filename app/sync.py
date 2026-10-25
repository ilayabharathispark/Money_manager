"""
sync.py — Orchestrator: reads emails → parses with AI → stores in database.
Run this manually or schedule it to keep your dashboard up to date.
"""

import sys
import os

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Make sure app/ modules are importable
sys.path.insert(0, os.path.dirname(__file__))

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from email_reader import fetch_bank_emails
from ai_parser import parse_email_with_ai
from database import init_db, insert_transaction, is_already_synced, get_all_synced_ids


def sync_emails(start_date: str = None, end_date: str = None, progress_callback=None, max_workers: int = 3):
    """
    Fetch new bank emails in a date range, parse them with AI concurrently, and save to database.
    Bounded to 3 workers for high reliability, accuracy, and rate-limit avoidance.
    progress_callback: optional callable(fraction: float, message: str) for live UI updates.
    """
    print("=" * 50)
    print("💳 Money Manager — Email Sync (Multi-threaded, 3 workers)")
    if start_date or end_date:
        print(f"   Range: {start_date or 'beginning'} → {end_date or 'today'}")
    print("=" * 50)

    # Ensure database exists
    init_db()

    if progress_callback:
        progress_callback(0.05, "Searching Gmail for bank alerts...")

    # Step 1: Get existing synced IDs to avoid downloading or parsing duplicates
    synced_ids = get_all_synced_ids()

    # Step 2: Fetch only new emails from Gmail (concurrently downloaded inside fetch_bank_emails)
    emails = fetch_bank_emails(
        start_date=start_date,
        end_date=end_date,
        already_synced_ids=synced_ids,
        max_workers=max_workers,
    )
    if not emails:
        print("\n✅ Nothing new to sync (all emails already in database).")
        if progress_callback:
            progress_callback(1.0, "All emails already up to date!")
        return {"inserted": 0, "skipped": 0, "total": 0}

    total_emails = len(emails)
    print(f"⚡ Parsing {total_emails} emails using {max_workers} AI workers (prioritizing accuracy)...")

    inserted = 0
    skipped_not_txn = 0
    completed_count = 0

    def _parse_and_insert(email):
        msg_id = email["msg_id"]
        # Mild spacing to prevent bursting rate limits
        time.sleep(0.3)
        parsed = parse_email_with_ai(email["body"])
        if parsed is None:
            return "not_txn", email
        txn = {
            "email_msg_id": msg_id,
            "date":         parsed.get("date", ""),
            "time":         parsed.get("time"),
            "type":         parsed.get("type", "debit"),
            "amount":       parsed.get("amount", 0.0),
            "merchant":     parsed.get("merchant", "Unknown"),
            "category":     parsed.get("category", "Other"),
            "balance":      parsed.get("balance"),
            "description":  parsed.get("description", ""),
            "raw_email":    email["body"],
        }
        success = insert_transaction(txn)
        return ("inserted" if success else "duplicate"), txn

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_parse_and_insert, em): em for em in emails}
        for future in as_completed(futures):
            completed_count += 1
            status, data = future.result()
            if status == "inserted":
                inserted += 1
                print(f"   ✅ [{completed_count}/{total_emails}] Saved: ₹{data['amount']} {data['type']} at {data['merchant']}")
            elif status == "not_txn":
                skipped_not_txn += 1
                print(f"   ⏭️  [{completed_count}/{total_emails}] Skipped non-transaction")

            if progress_callback:
                fraction = 0.15 + 0.85 * (completed_count / total_emails)
                progress_callback(fraction, f"Parsed {completed_count}/{total_emails} emails with AI...")

    print("\n" + "=" * 50)
    print(f"📊 Sync complete: {inserted} new saved | {skipped_not_txn} non-transaction")
    print("=" * 50)

    if progress_callback:
        progress_callback(1.0, f"Sync complete! Added {inserted} new transactions.")

    return {"inserted": inserted, "skipped": skipped_not_txn, "total": total_emails}


if __name__ == "__main__":
    sync_emails()
