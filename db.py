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
    user_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    company TEXT,
    title TEXT,
    phone TEXT,
    website TEXT,
    street_address TEXT,
    city TEXT,
    zip_code TEXT,
    google_rating REAL,
    review_count INTEGER,
    google_place_id TEXT,
    source TEXT DEFAULT 'manual',
    tags TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(email, user_id)
);

-- Email sequences (templates for multi-step campaigns)
CREATE TABLE IF NOT EXISTS sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(name, user_id)
);

-- Individual emails in a sequence
CREATE TABLE IF NOT EXISTS sequence_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    delay_days INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sequence_id) REFERENCES sequences(id),
    UNIQUE(sequence_id, step_number)
);

-- Track which contacts are in which sequences
CREATE TABLE IF NOT EXISTS contact_sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    sequence_id INTEGER NOT NULL,
    current_step INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
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
    resend_id TEXT UNIQUE,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
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
    event_type TEXT NOT NULL,
    data TEXT,
    received_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0
);

-- Reusable email templates
CREATE TABLE IF NOT EXISTS email_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    template_type TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Users for web app authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_api_owner INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_sequences_user ON sequences(user_id);
CREATE INDEX IF NOT EXISTS idx_templates_user ON email_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_contact_sequences_status ON contact_sequences(status);
CREATE INDEX IF NOT EXISTS idx_contact_sequences_next_send ON contact_sequences(next_send_at);
CREATE INDEX IF NOT EXISTS idx_emails_sent_resend_id ON emails_sent(resend_id);
CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed);
"""

OWNER_EMAIL = 'oskar.hurme@gmail.com'

def _column_exists(conn, table, column):
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols

def _migrate_add_user_id(conn):
    if _column_exists(conn, 'contacts', 'user_id'):
        return False

    print("Running multi-tenancy migration...")

    owner = conn.execute("SELECT id FROM users WHERE email = ?", (OWNER_EMAIL,)).fetchone()
    owner_id = owner[0] if owner else 0

    for table in ['contacts', 'sequences', 'email_templates']:
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")

    if not _column_exists(conn, 'users', 'is_api_owner'):
        conn.execute("ALTER TABLE users ADD COLUMN is_api_owner INTEGER DEFAULT 0")

    conn.executescript("""
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            company TEXT,
            title TEXT,
            source TEXT DEFAULT 'manual',
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(email, user_id)
        );

        CREATE TABLE sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(name, user_id)
        );

        CREATE TABLE email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            template_type TEXT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.execute("""
        INSERT INTO contacts (id, user_id, email, first_name, last_name, company, title, source, tags, created_at, updated_at)
        SELECT id, ?, email, first_name, last_name, company, title, source, tags, created_at, updated_at
        FROM contacts_old
    """, (owner_id,))
    conn.execute("""
        INSERT INTO sequences (id, user_id, name, description, created_at)
        SELECT id, ?, name, description, created_at
        FROM sequences_old
    """, (owner_id,))
    conn.execute("""
        INSERT INTO email_templates (id, user_id, name, template_type, subject, body, created_at)
        SELECT id, ?, name, template_type, subject, body, created_at
        FROM email_templates_old
    """, (owner_id,))

    if owner_id > 0:
        conn.execute("UPDATE users SET is_api_owner = 1 WHERE id = ?", (owner_id,))
        print(f"Migrated data to user {OWNER_EMAIL} (id={owner_id})")
    else:
        print(f"Owner user not found yet — data stored with placeholder user_id=0, will be assigned when {OWNER_EMAIL} registers")

    conn.execute("DROP TABLE contacts_old")
    conn.execute("DROP TABLE sequences_old")
    conn.execute("DROP TABLE email_templates_old")

    return True

def migrate_owner_data(conn):
    owner = conn.execute("SELECT id FROM users WHERE email = ?", (OWNER_EMAIL,)).fetchone()
    if not owner:
        return
    owner_id = owner[0]

    orphan_count = 0
    for table in ['contacts', 'sequences', 'email_templates']:
        count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = 0").fetchone()[0]
        if count > 0:
            conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id = 0", (owner_id,))
            orphan_count += count

    if orphan_count > 0:
        print(f"Assigned {orphan_count} orphan records to {OWNER_EMAIL}")

    conn.execute("UPDATE users SET is_api_owner = 1 WHERE id = ?", (owner_id,))

def init_db():
    """Initialize the database with schema and run migrations."""
    import sys
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, is_api_owner INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

        if table_exists(conn, 'contacts') and not _column_exists(conn, 'contacts', 'user_id'):
            print("[DB] Running multi-tenancy migration...", file=sys.stderr)
            _migrate_add_user_id(conn)
            conn.commit()
            print("[DB] Migration complete", file=sys.stderr)
        else:
            conn.executescript(SCHEMA)

        if not _column_exists(conn, 'users', 'is_api_owner'):
            conn.execute("ALTER TABLE users ADD COLUMN is_api_owner INTEGER DEFAULT 0")

        new_contact_columns = [
            ('phone', 'TEXT'),
            ('website', 'TEXT'),
            ('street_address', 'TEXT'),
            ('city', 'TEXT'),
            ('zip_code', 'TEXT'),
            ('google_rating', 'REAL'),
            ('review_count', 'INTEGER'),
            ('google_place_id', 'TEXT'),
        ]
        for col_name, col_type in new_contact_columns:
            if not _column_exists(conn, 'contacts', col_name):
                conn.execute(f"ALTER TABLE contacts ADD COLUMN {col_name} {col_type}")
                print(f"[DB] Added column contacts.{col_name}", file=sys.stderr)

        migrate_owner_data(conn)
        conn.commit()

        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        contact_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        print(f"[DB] Initialized: {user_count} users, {contact_count} contacts", file=sys.stderr)
    except Exception as e:
        print(f"[DB] ERROR during init: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()
    print(f"Database initialized at {DB_PATH}")

def table_exists(conn, table_name):
    result = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return result[0] > 0

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

def get_api_owner_user_id():
    """Get the user_id associated with the API key."""
    with get_db() as conn:
        owner = conn.execute("SELECT id FROM users WHERE is_api_owner = 1 LIMIT 1").fetchone()
        return owner['id'] if owner else None

if __name__ == "__main__":
    init_db()
