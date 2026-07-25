import sqlite3
import os
import random
import string
from datetime import datetime

import emailer

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "grievances.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            email TEXT NOT NULL,
            event TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def _generate_ticket_id(conn):
    year = datetime.now().year
    while True:
        suffix = "".join(random.choices(string.digits, k=5))
        ticket_id = f"GBU-{year}-{suffix}"
        exists = conn.execute(
            "SELECT 1 FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not exists:
            return ticket_id

def create_ticket(name: str, email: str, category: str, description: str) -> str:
    conn = get_connection()
    ticket_id = _generate_ticket_id(conn)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO tickets (ticket_id, name, email, category, description, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?)",
        (ticket_id, name, email, category, description, now, now),
    )
    _log_notification(
        conn, ticket_id, email, "Grievance Submitted",
        name=name, category=category,
    )
    conn.commit()
    conn.close()
    return ticket_id

def get_ticket(ticket_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id.upper(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def update_status(ticket_id: str, status: str) -> bool:
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
        (status, now, ticket_id.upper()),
    )
    if cur.rowcount:
        ticket = conn.execute(
            "SELECT name, email FROM tickets WHERE ticket_id = ?", (ticket_id.upper(),)
        ).fetchone()
        _log_notification(
            conn, ticket_id.upper(), ticket["email"], f"Status Updated: {status}",
            name=ticket["name"], status=status,
        )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated

def _log_notification(conn, ticket_id, email, event, **template_fields):
    delivered = emailer.send_email(event, email, ticket_id=ticket_id, **template_fields)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO notifications (ticket_id, email, event, sent_at, delivered) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, email, event, now, int(delivered)),
    )
    
def list_notifications_for(ticket_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE ticket_id = ? ORDER BY sent_at",
        (ticket_id.upper(),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
