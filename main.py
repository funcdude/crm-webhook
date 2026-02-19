"""
Simple CRM - Flask Web App + Webhook Receiver

Runs on Replit with:
- Web UI for managing contacts and sequences
- Webhook endpoint for Resend events
- Email sending via Resend API
"""
import os
import re
import csv
import json
import hmac
import hashlib
import io
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from db import get_db, init_db, dict_from_row

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

# Configuration from environment
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'Oskar Hurme <oskar@oskarhurme.com>')
REPLY_TO = os.environ.get('REPLY_TO', 'oskar@oskarhurme.com')
WEBHOOK_API_KEY = os.environ.get('WEBHOOK_API_KEY', '')
RESEND_WEBHOOK_SECRET = os.environ.get('RESEND_WEBHOOK_SECRET', '')

# Initialize Resend if available
resend = None
if RESEND_API_KEY:
    try:
        import resend as resend_lib
        resend_lib.api_key = RESEND_API_KEY
        resend = resend_lib
    except ImportError:
        print("⚠️ Resend library not installed")

# Initialize database on startup
init_db()

# ============== Helper Functions ==============

def personalize(template: str, contact: dict) -> str:
    """Replace placeholders in template with contact data."""
    result = template
    replacements = {
        '{first_name}': contact.get('first_name') or 'there',
        '{last_name}': contact.get('last_name') or '',
        '{company}': contact.get('company') or 'your company',
        '{email}': contact.get('email') or '',
        '{title}': contact.get('title') or '',
    }
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Resend webhook signature."""
    if not RESEND_WEBHOOK_SECRET:
        return True
    expected = hmac.new(
        RESEND_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

# ============== Web Routes ==============

@app.route('/')
def index():
    """Dashboard homepage."""
    with get_db() as conn:
        contact_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        sequence_count = conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0]
        active_enrollments = conn.execute(
            "SELECT COUNT(*) FROM contact_sequences WHERE status = 'active'"
        ).fetchone()[0]
        emails_sent = conn.execute("SELECT COUNT(*) FROM emails_sent").fetchone()[0]
        
        # Recent activity
        recent_emails = conn.execute("""
            SELECT e.*, c.email as contact_email, c.first_name
            FROM emails_sent e
            JOIN contacts c ON c.id = e.contact_id
            ORDER BY e.sent_at DESC LIMIT 10
        """).fetchall()
        
        # Pending sends
        pending = conn.execute("""
            SELECT COUNT(*) FROM contact_sequences 
            WHERE status = 'active' AND next_send_at <= datetime('now')
        """).fetchone()[0]
    
    return render_template('index.html',
        contact_count=contact_count,
        sequence_count=sequence_count,
        active_enrollments=active_enrollments,
        emails_sent=emails_sent,
        recent_emails=recent_emails,
        pending=pending,
        resend_configured=bool(RESEND_API_KEY)
    )

@app.route('/contacts')
def contacts():
    """List all contacts."""
    tag = request.args.get('tag', '')
    with get_db() as conn:
        if tag:
            rows = conn.execute("""
                SELECT c.*, 
                    (SELECT COUNT(*) FROM contact_sequences cs WHERE cs.contact_id = c.id) as sequences,
                    (SELECT COUNT(*) FROM emails_sent es WHERE es.contact_id = c.id) as emails
                FROM contacts c
                WHERE c.tags LIKE ?
                ORDER BY c.created_at DESC
            """, (f"%{tag}%",)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.*, 
                    (SELECT COUNT(*) FROM contact_sequences cs WHERE cs.contact_id = c.id) as sequences,
                    (SELECT COUNT(*) FROM emails_sent es WHERE es.contact_id = c.id) as emails
                FROM contacts c
                ORDER BY c.created_at DESC
            """).fetchall()
        
        # Get all unique tags
        all_tags = set()
        for row in conn.execute("SELECT tags FROM contacts WHERE tags IS NOT NULL"):
            if row['tags']:
                all_tags.update(t.strip() for t in row['tags'].split(','))
    
    return render_template('contacts.html', contacts=rows, tags=sorted(all_tags), current_tag=tag)

@app.route('/contacts/import', methods=['GET', 'POST'])
def import_contacts():
    """Import contacts from CSV."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('import_contacts'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('import_contacts'))
        
        source = request.form.get('source', 'hunter')
        tags = request.form.get('tags', '').strip()
        
        # Parse CSV
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        
        imported = 0
        skipped = 0
        errors = []
        
        fieldnames_lower = {name.lower().strip(): name for name in reader.fieldnames} if reader.fieldnames else {}
        
        def get_csv_value(row, *possible_names):
            for name in possible_names:
                if name in fieldnames_lower:
                    val = row.get(fieldnames_lower[name], '').strip()
                    if val and val.upper() != 'N/A':
                        return val
            return None
        
        with get_db() as conn:
            for row in reader:
                email = get_csv_value(row, 'email', 'work email', 'work_email', 'e-mail', 'email address')
                if not email:
                    email = get_csv_value(row, 'personal email', 'personal_email')
                if email:
                    email = email.lower()
                
                first_name = get_csv_value(row, 'first_name', 'first name', 'firstname')
                last_name = get_csv_value(row, 'last_name', 'last name', 'lastname')
                
                if not first_name and not last_name:
                    full_name = get_csv_value(row, 'name', 'full name', 'full_name', 'contact name', 'contact_name')
                    if full_name:
                        parts = full_name.split(None, 1)
                        first_name = parts[0]
                        last_name = parts[1] if len(parts) > 1 else None
                
                company = get_csv_value(row, 'company', 'organization', 'company name', 'company_name', 'org')
                title = get_csv_value(row, 'title', 'position', 'job title', 'job_title', 'role')
                
                if not email:
                    continue
                
                try:
                    existing = conn.execute("SELECT id FROM contacts WHERE email = ?", (email,)).fetchone()
                    conn.execute("""
                        INSERT INTO contacts (email, first_name, last_name, company, title, source, tags)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(email) DO UPDATE SET
                            first_name = COALESCE(excluded.first_name, first_name),
                            last_name = COALESCE(excluded.last_name, last_name),
                            company = COALESCE(excluded.company, company),
                            title = COALESCE(excluded.title, title),
                            updated_at = CURRENT_TIMESTAMP
                    """, (email, first_name, last_name, company, title, source, tags))
                    if existing:
                        skipped += 1
                    else:
                        imported += 1
                except Exception as e:
                    errors.append(str(e))
        
        msg = f'Imported {imported} new contacts'
        if skipped:
            msg += f', {skipped} duplicates updated'
        flash(msg, 'success')
        return redirect(url_for('contacts'))
    
    return render_template('import.html')

@app.route('/contacts/<int:contact_id>/edit', methods=['POST'])
def edit_contact(contact_id):
    email = request.form.get('email', '').strip().lower()
    first_name = request.form.get('first_name', '').strip() or None
    last_name = request.form.get('last_name', '').strip() or None
    company = request.form.get('company', '').strip() or None
    title = request.form.get('title', '').strip() or None
    
    if not email:
        flash('Email is required', 'error')
        return redirect(url_for('contacts'))
    
    with get_db() as conn:
        conn.execute("""
            UPDATE contacts SET email = ?, first_name = ?, last_name = ?, 
                company = ?, title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (email, first_name, last_name, company, title, contact_id))
    
    flash('Contact updated', 'success')
    return redirect(url_for('contacts'))

@app.route('/contacts/<int:contact_id>/delete', methods=['POST'])
def delete_contact(contact_id):
    with get_db() as conn:
        conn.execute("DELETE FROM contact_sequences WHERE contact_id = ?", (contact_id,))
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    flash('Contact deleted', 'success')
    return redirect(url_for('contacts'))

@app.route('/sequences')
def sequences():
    """List all sequences."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.*, 
                COUNT(DISTINCT ss.id) as steps,
                COUNT(DISTINCT CASE WHEN cs.status = 'active' THEN cs.id END) as active,
                COUNT(DISTINCT CASE WHEN cs.status = 'replied' THEN cs.id END) as replied
            FROM sequences s
            LEFT JOIN sequence_steps ss ON ss.sequence_id = s.id
            LEFT JOIN contact_sequences cs ON cs.sequence_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """).fetchall()
    return render_template('sequences.html', sequences=rows)

@app.route('/sequences/new', methods=['GET', 'POST'])
def new_sequence():
    """Create a new sequence."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('new_sequence'))
        
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO sequences (name, description) VALUES (?, ?)",
                (name, description)
            )
            seq_id = cursor.lastrowid
        
        flash(f'Created sequence "{name}"', 'success')
        return redirect(url_for('edit_sequence', seq_id=seq_id))
    
    return render_template('sequence_new.html')

@app.route('/sequences/<int:seq_id>')
def edit_sequence(seq_id):
    """Edit a sequence."""
    with get_db() as conn:
        seq = conn.execute("SELECT * FROM sequences WHERE id = ?", (seq_id,)).fetchone()
        if not seq:
            flash('Sequence not found', 'error')
            return redirect(url_for('sequences'))
        
        steps = conn.execute("""
            SELECT * FROM sequence_steps WHERE sequence_id = ? ORDER BY step_number
        """, (seq_id,)).fetchall()
        
        enrollments = conn.execute("""
            SELECT cs.*, c.email, c.first_name, c.last_name
            FROM contact_sequences cs
            JOIN contacts c ON c.id = cs.contact_id
            WHERE cs.sequence_id = ?
            ORDER BY cs.started_at DESC
            LIMIT 50
        """, (seq_id,)).fetchall()
    
    return render_template('sequence_edit.html', sequence=seq, steps=steps, enrollments=enrollments)

@app.route('/sequences/<int:seq_id>/steps', methods=['POST'])
def add_step(seq_id):
    """Add a step to a sequence."""
    step_number = int(request.form.get('step_number', 1))
    delay_days = int(request.form.get('delay_days', 0))
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    
    if not subject or not body:
        flash('Subject and body are required', 'error')
        return redirect(url_for('edit_sequence', seq_id=seq_id))
    
    with get_db() as conn:
        conn.execute("""
            INSERT INTO sequence_steps (sequence_id, step_number, delay_days, subject, body)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sequence_id, step_number) DO UPDATE SET
                delay_days = excluded.delay_days,
                subject = excluded.subject,
                body = excluded.body
        """, (seq_id, step_number, delay_days, subject, body))
    
    flash(f'Added step {step_number}', 'success')
    return redirect(url_for('edit_sequence', seq_id=seq_id))

@app.route('/sequences/<int:seq_id>/enroll', methods=['POST'])
def enroll_contacts(seq_id):
    """Enroll contacts in a sequence."""
    tag = request.form.get('tag', '').strip()
    
    with get_db() as conn:
        if tag:
            contacts = conn.execute(
                "SELECT id, email FROM contacts WHERE tags LIKE ?",
                (f"%{tag}%",)
            ).fetchall()
        else:
            # Get selected contacts from form
            contact_ids = request.form.getlist('contact_ids')
            if not contact_ids:
                flash('No contacts selected', 'error')
                return redirect(url_for('edit_sequence', seq_id=seq_id))
            contacts = conn.execute(
                f"SELECT id, email FROM contacts WHERE id IN ({','.join('?' * len(contact_ids))})",
                contact_ids
            ).fetchall()
        
        enrolled = 0
        for contact in contacts:
            existing = conn.execute("""
                SELECT id, status FROM contact_sequences 
                WHERE contact_id = ? AND sequence_id = ?
            """, (contact['id'], seq_id)).fetchone()
            
            if existing and existing['status'] == 'active':
                continue
            
            if existing:
                conn.execute("""
                    UPDATE contact_sequences 
                    SET status = 'active', current_step = 0, 
                        next_send_at = datetime('now'),
                        updated_at = datetime('now')
                    WHERE id = ?
                """, (existing['id'],))
            else:
                conn.execute("""
                    INSERT INTO contact_sequences (contact_id, sequence_id, next_send_at)
                    VALUES (?, ?, datetime('now'))
                """, (contact['id'], seq_id))
            enrolled += 1
        
        flash(f'Enrolled {enrolled} contacts', 'success')
    
    return redirect(url_for('edit_sequence', seq_id=seq_id))

@app.route('/send', methods=['GET', 'POST'])
def send_emails():
    """Send due sequence emails."""
    with get_db() as conn:
        due_emails = conn.execute("""
            SELECT 
                cs.id as enrollment_id,
                cs.contact_id,
                cs.sequence_id,
                cs.current_step,
                c.email,
                c.first_name,
                c.last_name,
                c.company,
                c.title,
                ss.step_number,
                ss.subject,
                ss.body,
                s.name as sequence_name
            FROM contact_sequences cs
            JOIN contacts c ON c.id = cs.contact_id
            JOIN sequences s ON s.id = cs.sequence_id
            JOIN sequence_steps ss ON ss.sequence_id = cs.sequence_id 
                AND ss.step_number = cs.current_step + 1
            WHERE cs.status = 'active'
                AND cs.next_send_at <= datetime('now')
        """).fetchall()
    
    if request.method == 'POST' and resend:
        sent = 0
        for email in due_emails:
            contact = {
                'first_name': email['first_name'],
                'last_name': email['last_name'],
                'company': email['company'],
                'email': email['email'],
                'title': email['title'],
            }
            
            subject = personalize(email['subject'], contact)
            body = personalize(email['body'], contact)
            
            try:
                response = resend.Emails.send({
                    "from": FROM_EMAIL,
                    "to": [email['email']],
                    "reply_to": REPLY_TO,
                    "subject": subject,
                    "text": body,
                })
                
                resend_id = response.get('id') if isinstance(response, dict) else getattr(response, 'id', None)
                
                with get_db() as conn:
                    # Log the email
                    conn.execute("""
                        INSERT INTO emails_sent 
                        (contact_id, sequence_id, step_number, resend_id, subject, body)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (email['contact_id'], email['sequence_id'], email['step_number'], 
                          resend_id, subject, body))
                    
                    # Update sequence progress
                    next_step = conn.execute("""
                        SELECT delay_days FROM sequence_steps 
                        WHERE sequence_id = ? AND step_number = ?
                    """, (email['sequence_id'], email['step_number'] + 1)).fetchone()
                    
                    if next_step:
                        next_send = datetime.now() + timedelta(days=next_step['delay_days'])
                        conn.execute("""
                            UPDATE contact_sequences 
                            SET current_step = ?,
                                last_sent_at = datetime('now'),
                                next_send_at = ?,
                                updated_at = datetime('now')
                            WHERE id = ?
                        """, (email['step_number'], next_send.isoformat(), email['enrollment_id']))
                    else:
                        conn.execute("""
                            UPDATE contact_sequences 
                            SET current_step = ?,
                                status = 'completed',
                                last_sent_at = datetime('now'),
                                next_send_at = NULL,
                                updated_at = datetime('now')
                            WHERE id = ?
                        """, (email['step_number'], email['enrollment_id']))
                
                sent += 1
            except Exception as e:
                flash(f'Error sending to {email["email"]}: {e}', 'error')
        
        flash(f'Sent {sent} emails', 'success')
        return redirect(url_for('send_emails'))
    
    return render_template('send.html', due_emails=due_emails, resend_configured=bool(resend))

@app.route('/stats')
def stats():
    """Email statistics."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails_sent").fetchone()[0]
        by_status = conn.execute("""
            SELECT status, COUNT(*) as count FROM emails_sent GROUP BY status
        """).fetchall()
        
        replied = conn.execute(
            "SELECT COUNT(*) FROM emails_sent WHERE replied_at IS NOT NULL"
        ).fetchone()[0]
        
        by_sequence = conn.execute("""
            SELECT s.name, 
                COUNT(DISTINCT es.id) as sent,
                COUNT(DISTINCT CASE WHEN es.status = 'opened' THEN es.id END) as opened,
                COUNT(DISTINCT CASE WHEN es.replied_at IS NOT NULL THEN es.id END) as replied
            FROM sequences s
            LEFT JOIN emails_sent es ON es.sequence_id = s.id
            GROUP BY s.id
        """).fetchall()
    
    return render_template('stats.html', 
        total=total, 
        by_status=by_status, 
        replied=replied,
        by_sequence=by_sequence
    )

# ============== Email Templates ==============

@app.route('/templates')
def email_templates():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM email_templates ORDER BY template_type, created_at DESC
        """).fetchall()
        types = conn.execute("""
            SELECT DISTINCT template_type FROM email_templates 
            WHERE template_type IS NOT NULL ORDER BY template_type
        """).fetchall()
    return render_template('email_templates.html', templates=rows, types=[t['template_type'] for t in types])

@app.route('/templates/new', methods=['POST'])
def new_template():
    name = request.form.get('name', '').strip()
    template_type = request.form.get('template_type', '').strip() or None
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    
    if not name or not subject or not body:
        flash('Name, subject and body are required', 'error')
        return redirect(url_for('email_templates'))
    
    with get_db() as conn:
        conn.execute("""
            INSERT INTO email_templates (name, template_type, subject, body)
            VALUES (?, ?, ?, ?)
        """, (name, template_type, subject, body))
    
    flash(f'Created template "{name}"', 'success')
    return redirect(url_for('email_templates'))

@app.route('/templates/import', methods=['POST'])
def import_templates():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('email_templates'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('email_templates'))
    
    try:
        content = file.read().decode('utf-8-sig')
        data = json.loads(content)
        
        if not isinstance(data, list):
            data = [data]
        
        imported = 0
        with get_db() as conn:
            for item in data:
                subject = item.get('subject', '').strip()
                body = item.get('body', '').strip()
                if not subject or not body:
                    continue
                
                template_type = item.get('template_type', '').strip() or None
                name = item.get('contact_name') or item.get('name') or f"{template_type or 'email'} template"
                
                subject_template = subject
                body_template = body
                
                contact_name = item.get('contact_name', '')
                if contact_name:
                    parts = contact_name.split()
                    first = parts[0]
                    last = parts[-1] if len(parts) > 1 else ''
                    
                    greetings = ['Hi', 'Hey', 'Hello', 'Dear']
                    for g in greetings:
                        pattern = re.compile(re.escape(f'{g} {first}') + r'(?=[,\s!.\n]|$)')
                        body_template = pattern.sub(f'{g} {{first_name}}', body_template)
                    
                    if last and last != first:
                        body_template = body_template.replace(f'{first} {last}', '{first_name} {last_name}')
                
                company = item.get('company', '')
                if company:
                    subject_template = subject_template.replace(company, '{company}')
                    body_template = body_template.replace(company, '{company}')
                
                conn.execute("""
                    INSERT INTO email_templates (name, template_type, subject, body)
                    VALUES (?, ?, ?, ?)
                """, (name, template_type, subject_template, body_template))
                imported += 1
        
        flash(f'Imported {imported} templates', 'success')
    except json.JSONDecodeError:
        flash('Invalid JSON file', 'error')
    except Exception as e:
        flash(f'Import error: {e}', 'error')
    
    return redirect(url_for('email_templates'))

@app.route('/templates/<int:tpl_id>/edit', methods=['POST'])
def edit_template(tpl_id):
    name = request.form.get('name', '').strip()
    template_type = request.form.get('template_type', '').strip() or None
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    
    if not name or not subject or not body:
        flash('Name, subject and body are required', 'error')
        return redirect(url_for('email_templates'))
    
    with get_db() as conn:
        conn.execute("""
            UPDATE email_templates SET name = ?, template_type = ?, subject = ?, body = ?
            WHERE id = ?
        """, (name, template_type, subject, body, tpl_id))
    
    flash('Template updated', 'success')
    return redirect(url_for('email_templates'))

@app.route('/templates/<int:tpl_id>/delete', methods=['POST'])
def delete_template(tpl_id):
    with get_db() as conn:
        conn.execute("DELETE FROM email_templates WHERE id = ?", (tpl_id,))
    flash('Template deleted', 'success')
    return redirect(url_for('email_templates'))

@app.route('/api/templates')
def api_templates():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM email_templates ORDER BY template_type, name").fetchall()
    return jsonify([dict(r) for r in rows])

# ============== Sequence Test Runner ==============

@app.route('/test-sequence')
def test_sequence():
    with get_db() as conn:
        all_sequences = conn.execute("""
            SELECT s.*, COUNT(ss.id) as step_count 
            FROM sequences s
            LEFT JOIN sequence_steps ss ON ss.sequence_id = s.id
            GROUP BY s.id ORDER BY s.name
        """).fetchall()
        all_contacts = conn.execute(
            "SELECT id, email, first_name, last_name, company, title FROM contacts ORDER BY email"
        ).fetchall()
        
        previews = []
        selected_seq = request.args.get('sequence_id', type=int)
        selected_contact = request.args.get('contact_id', type=int)
        contact_data = None
        
        if selected_seq and selected_contact:
            contact_row = conn.execute(
                "SELECT * FROM contacts WHERE id = ?", (selected_contact,)
            ).fetchone()
            if contact_row:
                contact_data = dict(contact_row)
                steps = conn.execute("""
                    SELECT * FROM sequence_steps WHERE sequence_id = ? ORDER BY step_number
                """, (selected_seq,)).fetchall()
                for step in steps:
                    previews.append({
                        'step_number': step['step_number'],
                        'delay_days': step['delay_days'],
                        'subject_raw': step['subject'],
                        'body_raw': step['body'],
                        'subject': personalize(step['subject'], contact_data),
                        'body': personalize(step['body'], contact_data),
                    })
    
    return render_template('test_sequence.html',
        sequences=all_sequences,
        contacts=all_contacts,
        previews=previews,
        selected_seq=selected_seq,
        selected_contact=selected_contact,
        contact_data=contact_data,
        resend_configured=bool(resend)
    )

@app.route('/test-sequence/send', methods=['POST'])
def test_send_email():
    if not resend:
        flash('Resend is not configured', 'error')
        return redirect(url_for('test_sequence'))
    
    to_email = request.form.get('to_email', '').strip()
    step_num = request.form.get('step_number', type=int)
    seq_id = request.form.get('sequence_id', type=int)
    contact_id = request.form.get('contact_id', type=int)
    
    if not to_email or not step_num or not seq_id or not contact_id:
        flash('Missing email details', 'error')
        return redirect(url_for('test_sequence'))
    
    with get_db() as conn:
        contact_row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        step_row = conn.execute("""
            SELECT * FROM sequence_steps WHERE sequence_id = ? AND step_number = ?
        """, (seq_id, step_num)).fetchone()
    
    if not contact_row or not step_row:
        flash('Contact or step not found', 'error')
        return redirect(url_for('test_sequence', sequence_id=seq_id, contact_id=contact_id))
    
    contact_data = dict(contact_row)
    subject = personalize(step_row['subject'], contact_data)
    body = personalize(step_row['body'], contact_data)
    
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "reply_to": REPLY_TO,
            "subject": f"[TEST] {subject}",
            "text": body,
        })
        flash(f'Test email for Step {step_num} sent to {to_email}', 'success')
    except Exception as e:
        flash(f'Send error: {e}', 'error')
    
    return redirect(url_for('test_sequence', sequence_id=seq_id, contact_id=contact_id))

# ============== Webhook Endpoint ==============

@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """Receive webhook events from Resend."""
    signature = request.headers.get('svix-signature', '')
    if RESEND_WEBHOOK_SECRET and not verify_webhook_signature(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        data = request.json
        event_type = data.get('type', 'unknown')
        event_data = data.get('data', {})
        resend_id = event_data.get('email_id') or event_data.get('id')
        
        with get_db() as conn:
            # Store the event
            conn.execute("""
                INSERT INTO events (resend_id, event_type, data, received_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (resend_id, event_type, json.dumps(event_data)))
            
            # Find the email record
            email_record = conn.execute("""
                SELECT id, contact_id, sequence_id FROM emails_sent 
                WHERE resend_id = ?
            """, (resend_id,)).fetchone()
            
            if email_record:
                now = datetime.now().isoformat()
                
                if event_type == 'email.delivered':
                    conn.execute("""
                        UPDATE emails_sent SET status = 'delivered', delivered_at = ? WHERE id = ?
                    """, (now, email_record['id']))
                    
                elif event_type == 'email.opened':
                    conn.execute("""
                        UPDATE emails_sent SET status = 'opened', opened_at = ? WHERE id = ?
                    """, (now, email_record['id']))
                    
                elif event_type == 'email.clicked':
                    conn.execute("""
                        UPDATE emails_sent SET status = 'clicked', clicked_at = ? WHERE id = ?
                    """, (now, email_record['id']))
                    
                elif event_type == 'email.bounced':
                    conn.execute("""
                        UPDATE emails_sent SET status = 'bounced' WHERE id = ?
                    """, (email_record['id'],))
                    if email_record['sequence_id']:
                        conn.execute("""
                            UPDATE contact_sequences 
                            SET status = 'bounced', updated_at = datetime('now')
                            WHERE contact_id = ? AND sequence_id = ?
                        """, (email_record['contact_id'], email_record['sequence_id']))
                    
                elif event_type == 'email.received':
                    # Reply received - stop the sequence!
                    conn.execute("""
                        UPDATE emails_sent SET replied_at = ? WHERE id = ?
                    """, (now, email_record['id']))
                    conn.execute("""
                        UPDATE contact_sequences 
                        SET status = 'replied', updated_at = datetime('now')
                        WHERE contact_id = ? AND status = 'active'
                    """, (email_record['contact_id'],))
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

# ============== API Endpoints ==============

@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'resend_configured': bool(RESEND_API_KEY),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
