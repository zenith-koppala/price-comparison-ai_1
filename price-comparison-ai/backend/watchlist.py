"""
watchlist.py
Persistence layer for the watchlist / price-drop alert feature.

Uses SQLite (stdlib, zero extra dependencies) keyed by an anonymous
session id stored in a signed Flask session cookie -- no login system
needed for a demo, but the data genuinely persists across visits from
the same browser.

Email alerts: if SMTP_HOST / SMTP_USER / SMTP_PASS environment variables
are set, a real email is sent via smtplib when a tracked product's price
drops to or below the target. If they aren't set (e.g. running the demo
without your own mail credentials), the alert is logged to the console
instead of failing silently -- the code path is real either way.
"""
import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "watchlist.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            target_price REAL NOT NULL,
            email TEXT,
            notified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_item(session_id: str, product_id: int, target_price: float, email: str | None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO watchlist (session_id, product_id, target_price, email, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, product_id, target_price, email, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def list_items(session_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE session_id = ? ORDER BY created_at DESC", (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_item(session_id: str, item_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE id = ? AND session_id = ?", (item_id, session_id))
    conn.commit()
    conn.close()


def all_unnotified_items():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM watchlist WHERE notified = 0").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified(item_id: int):
    conn = get_conn()
    conn.execute("UPDATE watchlist SET notified = 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def send_alert_email(to_email: str, product_name: str, current_price: float, target_price: float) -> bool:
    """Returns True if a real email was sent, False if it was only logged (no SMTP configured)."""
    subject = f"Price drop: {product_name} is now ₹{current_price:,.0f}"
    body = (
        f"Good news!\n\n{product_name} has dropped to ₹{current_price:,.0f}, "
        f"at or below your target of ₹{target_price:,.0f}.\n\n"
        f"— PricePilot"
    )

    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", 587))

    if not (host and user and password and to_email):
        print(f"[watchlist] (no SMTP configured) would email {to_email}: {subject}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[watchlist] email send failed: {e}")
        return False
