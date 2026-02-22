# SimpleCRM — MVP v0.5

## Overview

SimpleCRM is a lightweight email outreach CRM built with Flask and SQLite. It enables users to import contacts (primarily from Hunter.io CSV exports), create multi-step email sequences with automatic follow-ups, and track email engagement (opens, clicks, replies, bounces) via Resend webhooks. The system automatically stops sequences when a contact replies or an email bounces.

The app is designed to run on Replit as a single-process web application with a server-rendered UI.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend: Flask (Python)
- **Framework**: Flask serves both the web UI and the webhook API endpoint
- **Why Flask**: Lightweight, minimal boilerplate, well-suited for a single-file application pattern
- **Entry point**: `main.py` contains all routes, business logic, and email sending functionality
- **Server**: Gunicorn is specified in requirements for production serving

### Database: SQLite
- **Storage**: Single SQLite file (`crm.db`) managed through `db.py`
- **Schema**: Defined as raw SQL in `db.py` with `CREATE TABLE IF NOT EXISTS` for auto-initialization
- **Tables**:
  - `contacts` - Imported contacts with email, name, company, title, tags, source
  - `sequences` - Named multi-step email campaigns
  - `sequence_steps` - Individual steps within a sequence (step number, delay days, subject, body template)
  - `contact_sequences` - Junction table tracking which contacts are enrolled in which sequences, their current step, and status
  - `sent_emails` - Log of all sent emails with Resend message IDs for webhook correlation
  - `email_templates` - Reusable email templates with template types
- **Access pattern**: Context manager (`get_db`) for connections, `dict_from_row` helper for converting rows to dictionaries
- **Note**: If migrating to Postgres via Drizzle later, the schema is straightforward relational with no SQLite-specific features beyond the file-based storage

### Frontend: Server-rendered Jinja2 templates with Tailwind CSS
- **Templating**: Jinja2 templates in `templates/` directory, extending `base.html`
- **Styling**: Tailwind CSS loaded via CDN (`cdn.tailwindcss.com`)
- **No JavaScript framework**: Minimal client-side JS, standard HTML forms for all interactions
- **Pages**: Dashboard (`index.html`), Contacts list + Import (`contacts.html`, `import.html`), Sequences list + Edit + New (`sequences.html`, `sequence_edit.html`, `sequence_new.html`), Email Templates (`email_templates.html`), Test Sequence Runner (`test_sequence.html`), Send Queue (`send.html`), Statistics (`stats.html`)

### Email Sending
- **Provider**: Resend API via the `resend` Python library
- **Personalization**: Template variables like `{first_name}`, `{company}` are replaced at send time
- **Sequence logic**: Emails are scheduled based on `delay_days` relative to the previous step (step 1 = immediate, step 2 = +3 days, step 3 = +4 days typical pattern)
- **Send queue**: The `/send` page shows emails that are due based on timing, with a "Send All" button

### Webhook Processing
- **Endpoint**: `POST /webhook` receives Resend webhook events
- **Events handled**: `email.delivered`, `email.opened`, `email.clicked`, `email.bounced`, `email.received` (for reply detection)
- **Auto-stop**: When a reply or bounce is detected, the contact's sequence is automatically paused/stopped
- **Security**: Optional HMAC signature verification via `RESEND_WEBHOOK_SECRET`

### Web Authentication
- **User accounts**: Email/password authentication stored in `users` table
- **Password hashing**: `werkzeug.security` (pbkdf2:sha256) for password storage
- **Password policy**: Min 12 chars, 1 uppercase, 1 lowercase, 1 number, 1 special character
- **Session management**: Flask sessions with 7-day lifetime, httponly cookies, SameSite=Lax
- **Route protection**: `before_request` hook redirects unauthenticated users to `/login`; API endpoints (`/api/*`), webhooks (`/webhook`), static files, and Swagger docs are exempt
- **Pages**: Login (`/login`), Register (`/register`), Logout (`/logout`)

### Configuration
All configuration is via environment variables (Replit Secrets):
- `RESEND_API_KEY` - Resend API key for sending emails
- `FROM_EMAIL` - Sender address with display name
- `REPLY_TO` - Reply-to address
- `SECRET_KEY` - Flask session security key
- `WEBHOOK_API_KEY` - Optional API key for webhook endpoint
- `RESEND_WEBHOOK_SECRET` - Optional HMAC secret for webhook verification
- `DB_PATH` - SQLite database file path (defaults to `crm.db`)
- `CRM_API_KEY` - Shared API key for bot/external access to the REST API

### REST API for Bot Integration
All API endpoints (except `/api/health`) require `Authorization: Bearer <CRM_API_KEY>` header.

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check (no auth needed) |
| `/api/contacts` | GET | List contacts (supports `search`, `tag`, `limit`, `offset` params) |
| `/api/contacts` | POST | Add/update a single contact (JSON body with `email` required) |
| `/api/contacts/bulk` | POST | Add/update multiple contacts (JSON body with `contacts` array) |
| `/api/contacts/<id>` | GET | Get a single contact with their sequence enrollments |
| `/api/contacts/<id>/sequences` | GET | Check all sequence enrollments for a contact |
| `/api/contacts/<id>/sequences/<seq_id>/stop` | POST | Stop a contact's active sequence |
| `/api/sequences` | GET | List all sequences with step counts and enrollment counts |
| `/api/sequences/<id>` | GET | Get sequence details with steps and enrollments |
| `/api/sequences/<id>/enroll` | POST | Enroll a contact (JSON: `contact_id` or `email`) |
| `/api/sequences/<id>/enroll/bulk` | POST | Enroll multiple contacts (JSON: `contact_ids` array) |

See `bot_example.py` for a complete Python example showing how to use these endpoints.

## External Dependencies

### Python Packages (requirements.txt)
- **Flask** (>=2.0.0) - Web framework
- **Gunicorn** (>=20.0.0) - WSGI HTTP server for production
- **Resend** (>=2.0.0) - Email sending API client

### External Services
- **Resend** (resend.com) - Email delivery service. Requires domain verification (SPF + DKIM DNS records). Used for both sending emails and receiving delivery/engagement webhooks.
- **Hunter.io** - Not directly integrated via API, but the CSV import is designed to accept various CSV formats including Hunter.io exports. Supports flexible column mapping (Name, Work Email, Personal Email, Company, Title, etc.)

## Version History
- **MVP v0.5** (2026-02-22): Web UI authentication — email/password login/register with strong password policy, secure sessions, route protection
- **MVP v0.4** (2026-02-22): REST API with key authentication for bot integration — contacts CRUD, sequence enrollment, status checks
- **MVP v0.3** (2026-02-19): Test Sequence Runner, inline editing for contacts & templates, column sorting, nav highlight fixes
- **MVP v0.2** (2026-02-17): Email templates, improved CSV import, Resend integration verified
- **MVP v0.1**: Initial CRM with contacts, sequences, send queue, webhooks, stats

## Recent Changes
- 2026-02-22: Added web UI authentication — email/password login and registration with password hashing, strong password validation (12+ chars, mixed case, number, special char), 7-day sessions with httponly cookies, nav bar shows logged-in user email and logout link.
- 2026-02-22: Added REST API with Bearer token authentication for bot integration. Endpoints for contacts (list, add, bulk add), sequences (list, detail, enroll, bulk enroll, stop), and status checks. Example bot script at `bot_example.py`.
- 2026-02-19: Added Test Sequence Runner page — preview personalized emails for any sequence + contact combination, and send test emails with [TEST] prefix. Server-side content generation for security.
- 2026-02-17: Verified Resend email sending works end-to-end (test email sent successfully)
- 2026-02-17: Added email templates feature - reusable templates that can be created manually or imported from JSON files, then applied to sequence steps via a dropdown picker. JSON import auto-converts personalized emails into templates with {first_name}, {company} placeholders.
- 2026-02-17: Improved CSV import to handle diverse column names (Name, Work Email, Personal Email, etc.) and skip N/A values.

### Data Files
- `attached_assets/` contains JSON files with pre-built campaign data that can be imported as templates through the UI