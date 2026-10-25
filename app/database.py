"""
database.py — SQLite storage for all bank transactions.
Creates the DB and table on first run. Handles insert + query.
"""

import sqlite3
import os
import sys
import threading
from datetime import datetime

_db_lock = threading.Lock()
_initialized = False

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "transactions.db")


def get_connection():
    """Return a robust SQLite connection configured with WAL mode and busy timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # access columns by name
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Create the transactions and tombstone tables if they don't exist yet."""
    global _initialized
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email_msg_id    TEXT UNIQUE,           -- Gmail message ID (prevents duplicates)
            date            TEXT NOT NULL,          -- ISO date: YYYY-MM-DD
            time            TEXT,                   -- HH:MM if available
            type            TEXT NOT NULL,          -- 'debit' or 'credit'
            amount          REAL NOT NULL,          -- transaction amount in INR
            merchant        TEXT,                   -- where money was spent
            category        TEXT,                   -- Food, Transport, Shopping, etc.
            balance         REAL,                   -- available balance after txn
            description     TEXT,                   -- raw description from email
            raw_email       TEXT,                   -- full original email body
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deleted_emails (
            email_msg_id    TEXT PRIMARY KEY,       -- Tombstone: deleted emails never re-sync
            deleted_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    if not _initialized:
        print(f"✅ Database ready at: {os.path.abspath(DB_PATH)}")
        _initialized = True


def mark_emails_as_deleted(email_msg_ids: list[str]):
    """Record email_msg_id values as deleted so they are never re-synced from Gmail."""
    if not email_msg_ids:
        return
    with _db_lock:
        conn = get_connection()
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO deleted_emails (email_msg_id) VALUES (?)",
                [(mid,) for mid in email_msg_ids if mid]
            )
            conn.commit()
        finally:
            conn.close()


def insert_transaction(txn: dict) -> bool:
    """
    Insert a parsed transaction. Returns True if inserted, False if duplicate.
    txn dict keys: email_msg_id, date, time, type, amount, merchant,
                   category, balance, description, raw_email
    """
    with _db_lock:
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO transactions
                    (email_msg_id, date, time, type, amount, merchant, category,
                     balance, description, raw_email)
                VALUES
                    (:email_msg_id, :date, :time, :type, :amount, :merchant, :category,
                     :balance, :description, :raw_email)
            """, txn)
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # email_msg_id already exists → duplicate, skip silently
            return False
        finally:
            conn.close()


def is_already_synced(email_msg_id: str) -> bool:
    """
    Check if an email has already been parsed and stored in the database or marked deleted.
    Used to skip Gemini API calls for emails we've already processed.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM transactions WHERE email_msg_id = ? UNION SELECT 1 FROM deleted_emails WHERE email_msg_id = ? LIMIT 1",
            (email_msg_id, email_msg_id)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_all_synced_ids() -> set[str]:
    """Return a set of all email_msg_id values present in the database or tombstone table."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT email_msg_id FROM transactions WHERE email_msg_id IS NOT NULL").fetchall()
        deleted = conn.execute("SELECT email_msg_id FROM deleted_emails").fetchall()
        return {r["email_msg_id"] for r in rows} | {r["email_msg_id"] for r in deleted}
    finally:
        conn.close()


def get_all_transactions(
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    txn_type: str = None,
) -> list[dict]:
    """
    Fetch transactions with optional filters.
    Dates should be 'YYYY-MM-DD' strings.
    """
    conn = get_connection()
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if txn_type and txn_type != "All":
        query += " AND type = ?"
        params.append(txn_type)

    query += " ORDER BY date DESC, time DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_summary_stats() -> dict:
    """Return aggregate stats: total spent, total income, balance change."""
    conn = get_connection()
    row = conn.execute("""
        SELECT
            SUM(CASE WHEN type='debit'  THEN amount ELSE 0 END) AS total_spent,
            SUM(CASE WHEN type='credit' THEN amount ELSE 0 END) AS total_income,
            COUNT(*) AS total_txns
        FROM transactions
    """).fetchone()
    conn.close()
    return dict(row)


def get_category_totals(start_date: str = None, end_date: str = None) -> list[dict]:
    """Return total spend per category (debits only), optionally filtered by date."""
    conn = get_connection()
    query = """
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE type = 'debit'
    """
    params = []
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " GROUP BY category ORDER BY total DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_daily_totals(start_date: str = None, end_date: str = None) -> list[dict]:
    """Return daily debit totals for trend charts."""
    conn = get_connection()
    query = """
        SELECT date, SUM(amount) AS total
        FROM transactions
        WHERE type = 'debit'
    """
    params = []
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " GROUP BY date ORDER BY date ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
