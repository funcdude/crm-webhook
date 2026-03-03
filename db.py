"""
Database setup and helpers for the CRM.
Uses PostgreSQL via psycopg2 for persistent storage across deployments.
"""
import os
import sys
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

DATABASE_URL = os.environ.get('DATABASE_URL', '')

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_api_owner INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email, user_id)
);

CREATE TABLE IF NOT EXISTS sequences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, user_id)
);

CREATE TABLE IF NOT EXISTS sequence_steps (
    id SERIAL PRIMARY KEY,
    sequence_id INTEGER NOT NULL REFERENCES sequences(id),
    step_number INTEGER NOT NULL,
    delay_days INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sequence_id, step_number)
);

CREATE TABLE IF NOT EXISTS contact_sequences (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    sequence_id INTEGER NOT NULL REFERENCES sequences(id),
    current_step INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sent_at TIMESTAMP,
    next_send_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(contact_id, sequence_id)
);

CREATE TABLE IF NOT EXISTS emails_sent (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    sequence_id INTEGER REFERENCES sequences(id),
    step_number INTEGER,
    resend_id TEXT UNIQUE,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    replied_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    resend_id TEXT,
    event_type TEXT NOT NULL,
    data TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS email_templates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    template_type TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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


def _get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    print("[DB] Initializing PostgreSQL database...", file=sys.stderr)
    conn = _get_connection()
    try:
        cur = conn.cursor()
        for statement in SCHEMA.split(';'):
            statement = statement.strip()
            if statement:
                cur.execute(statement)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM contacts")
        contact_count = cur.fetchone()[0]
        print(f"[DB] Initialized: {user_count} users, {contact_count} contacts", file=sys.stderr)
    except Exception as e:
        conn.rollback()
        print(f"[DB] ERROR during init: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


def migrate_owner_data(conn):
    owner = conn.execute("SELECT id FROM users WHERE email = %s", (OWNER_EMAIL,)).fetchone()
    if not owner:
        return
    owner_id = owner['id']

    orphan_count = 0
    for table in ['contacts', 'sequences', 'email_templates']:
        count = conn.execute(f"SELECT COUNT(*) as cnt FROM {table} WHERE user_id = 0").fetchone()['cnt']
        if count > 0:
            conn.execute(f"UPDATE {table} SET user_id = %s WHERE user_id = 0", (owner_id,))
            orphan_count += count

    if orphan_count > 0:
        print(f"Assigned {orphan_count} orphan records to {OWNER_EMAIL}")

    conn.execute("UPDATE users SET is_api_owner = 1 WHERE id = %s", (owner_id,))


class DictRow(dict):
    def __init__(self, data):
        super().__init__(data if data else {})
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PgCursorWrapper:
    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._savepoint_counter = 0
    
    def execute(self, query, params=None):
        self._cursor.execute(query, params)
        return self
    
    def savepoint(self, name=None):
        if not name:
            self._savepoint_counter += 1
            name = f"sp_{self._savepoint_counter}"
        self._cursor.execute(f"SAVEPOINT {name}")
        return name
    
    def release_savepoint(self, name):
        self._cursor.execute(f"RELEASE SAVEPOINT {name}")
    
    def rollback_to_savepoint(self, name):
        self._cursor.execute(f"ROLLBACK TO SAVEPOINT {name}")
    
    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DictRow(dict(row))
    
    def fetchall(self):
        rows = self._cursor.fetchall()
        return [DictRow(dict(r)) for r in rows]
    
    def __iter__(self):
        rows = self._cursor.fetchall()
        return iter([DictRow(dict(r)) for r in rows])
    
    @property
    def lastrowid(self):
        return self._cursor.fetchone()['id'] if self._cursor.description else None
    
    @property
    def description(self):
        return self._cursor.description


@contextmanager
def get_db():
    conn = _get_connection()
    wrapper = PgCursorWrapper(conn)
    try:
        yield wrapper
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_from_row(row):
    if row is None:
        return None
    return dict(row)


def get_api_owner_user_id():
    with get_db() as conn:
        owner = conn.execute("SELECT id FROM users WHERE is_api_owner = 1 LIMIT 1").fetchone()
        return owner['id'] if owner else None


if __name__ == "__main__":
    init_db()
