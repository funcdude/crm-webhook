"""
Database setup and helpers for the CRM.
"""
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get('DB_PATH', 'crm.db')

SCHEMA = """
-- Contacts imported from Hunter or other sources
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    company TEXT,
    title TEXT,
    source TEXT DEFAULT 'manual',
    tags TEXT,  -- comma-separated tags
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Email sequences (templates for multi-step campaigns)
CREATE TABLE IF NOT EXISTS sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Individual emails in a sequence
CREATE TABLE IF NOT EXISTS sequence_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,  -- 1, 2, 3...
    delay_days INTEGER NOT NULL,   -- days after previous step (0 for first)
    subject TEXT NOT NULL,
    body TEXT NOT NULL,  -- supports {first_name}, {company}, etc.
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sequence_id) REFERENCES sequences(id),
    UNIQUE(sequence_id, step_number)
);

-- Track which contacts are in which sequences
CREATE TABLE IF NOT EXISTS contact_sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    sequence_id INTEGER NOT NULL,
    current_step INTEGER DEFAULT 0,  -- 0 = not started, 1+ = completed steps
    status TEXT DEFAULT 'active',    -- active, completed, replied, bounced, stopped
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_sent_at TEXT,
    next_send_at TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contact_id) REFERENCES contacts(id),
    FOREIGN KEY (sequence_id) REFERENCES sequences(id),
    UNIQUE(contact_id, sequence_id)
);

-- Log of all sent emails
CREATE TABLE IF NOT EXISTS emails_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    sequence_id INTEGER,
    step_number INTEGER,
    resend_id TEXT UNIQUE,  -- Resend's email ID
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'sent',  -- sent, delivered, opened, clicked, bounced
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    delivered_at TEXT,
    opened_at TEXT,
    clicked_at TEXT,
    replied_at TEXT,
    FOREIGN KEY (contact_id) REFERENCES contacts(id),
    FOREIGN KEY (sequence_id) REFERENCES sequences(id)
);

-- Webhook events from Resend
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resend_id TEXT,
    event_type TEXT NOT NULL,  -- delivered, opened, clicked, bounced, replied
    data TEXT,  -- JSON payload
    received_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contact_sequences_status ON contact_sequences(status);
CREATE INDEX IF NOT EXISTS idx_contact_sequences_next_send ON contact_sequences(next_send_at);
CREATE INDEX IF NOT EXISTS idx_emails_sent_resend_id ON emails_sent(resend_id);
CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed);
"""

def init_db():
    """Initialize the database with schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialized at {DB_PATH}")

@contextmanager
def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def dict_from_row(row):
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(zip(row.keys(), row))

if __name__ == "__main__":
    init_db()
