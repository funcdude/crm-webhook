# Simple CRM

## Overview
A Flask-based CRM web application with contact management, email sequences, and Resend webhook integration. Features a web UI for managing contacts and campaigns, plus a webhook receiver for tracking email events (deliveries, opens, clicks, bounces, replies). Includes a ready-to-use OpenClaw skill for bot-driven access to the API.

## Current State
- Full CRM web UI running on port 5000 with dashboard, contacts, sequences, and stats pages
- SQLite database for persistent storage of contacts, sequences, emails, and events
- Resend API integration for sending emails
- Webhook receiver for Resend email event tracking
- CSV contact import support
- OpenClaw skill for bot integration included in `openclaw-skill/`

## Tech Stack
- **Language:** Python 3.11
- **Web Framework:** Flask (>=2.0.0)
- **WSGI Server:** Gunicorn (>=20.0.0, available for production use)
- **Email API:** Resend (>=2.0.0)
- **Database:** SQLite (file: `crm.db`)
- **Templates:** Jinja2 (HTML templates in `templates/`)
- **Port:** Configurable via `PORT` env var, defaults to 5000

## Project Structure
```
.
├── main.py                          # Flask app with web routes, API, and webhook handler
├── db.py                            # Database schema, init, and connection helpers
├── requirements.txt                 # Python dependencies (flask, gunicorn, resend)
├── .gitignore                       # Git ignore rules
├── README.md                        # Project README
├── replit.md                        # This file
├── templates/                       # Jinja2 HTML templates
│   ├── base.html                    # Base layout with navigation
│   ├── index.html                   # Dashboard with stats overview
│   ├── contacts.html                # Contact list with tag filtering
│   ├── import.html                  # CSV contact import
│   ├── send.html                    # Send email to a contact
│   ├── sequences.html               # List all email sequences
│   ├── sequence_new.html            # Create new sequence
│   ├── sequence_edit.html           # Edit sequence with steps
│   └── stats.html                   # Email delivery statistics
└── openclaw-skill/                  # OpenClaw bot skill
    ├── SKILL.md                     # Skill definition and instructions for OpenClaw
    └── scripts/
        └── crm_api.py               # Python CLI client for the webhook API
```

## Database Schema (SQLite)
- **contacts** — Email, name, company, title, source, tags
- **sequences** — Named email campaign sequences
- **sequence_steps** — Individual emails in a sequence with delay and template
- **contact_sequences** — Enrollment tracking (status: active/completed/replied/bounced/stopped)
- **emails_sent** — Log of all sent emails with delivery tracking (sent/delivered/opened/clicked/bounced)
- **events** — Raw webhook events from Resend

## Web UI Routes
| Path                        | Description                              |
|-----------------------------|------------------------------------------|
| `/`                         | Dashboard with stats and recent activity |
| `/contacts`                 | Contact list with tag filtering          |
| `/contacts/import`          | CSV contact import                       |
| `/contacts/<id>/send`       | Send email to a specific contact         |
| `/sequences`                | List all email sequences                 |
| `/sequences/new`            | Create a new sequence                    |
| `/sequences/<id>`           | Edit sequence and manage steps           |
| `/stats`                    | Email delivery statistics                |

## API Endpoints
| Method | Path              | Description                                         | Auth Required |
|--------|-------------------|-----------------------------------------------------|---------------|
| GET    | `/api/health`     | Health check with Resend config status               | No            |
| POST   | `/webhook`        | Receives webhook events from Resend                  | Signature (optional) |

## Environment Variables / Secrets
| Variable                | Purpose                                               | Required |
|-------------------------|-------------------------------------------------------|----------|
| `RESEND_API_KEY`        | Resend API key for sending emails                     | Yes (for sending) |
| `FROM_EMAIL`            | Sender email address                                  | Optional (has default) |
| `REPLY_TO`              | Reply-to email address                                | Optional (has default) |
| `WEBHOOK_API_KEY`       | API key for authenticating webhook/API requests       | Recommended |
| `RESEND_WEBHOOK_SECRET` | Resend webhook signing secret for signature verification | Optional |
| `SECRET_KEY`            | Flask session secret key                              | Optional (has default) |
| `DB_PATH`               | Path to SQLite database file                          | Optional (defaults to `crm.db`) |

## Key Behaviors
- Contacts can be imported via CSV with columns: email, first_name, last_name, company, title
- Email templates support personalization: `{first_name}`, `{last_name}`, `{company}`, `{email}`, `{title}`
- Sequences are multi-step email campaigns with configurable delays between steps
- Webhook events automatically update email delivery status and stop sequences on replies/bounces
- Database persists across restarts (SQLite file)

## OpenClaw Skill
The `openclaw-skill/` directory contains a ready-to-use OpenClaw skill for bot interaction with this CRM. To use it:

1. Copy the `openclaw-skill/` folder to your OpenClaw skills directory (e.g., `~/.openclaw/skills/crm-webhook/`)
2. Set environment variables in your OpenClaw config:
   - `CRM_WEBHOOK_URL` — base URL of this CRM app
   - `CRM_API_KEY` — the same value as `WEBHOOK_API_KEY`
3. The bot can check email events, search for bounces, get summaries, etc.

## Recent Changes
- 2026-02-17: Imported latest changes from GitHub — full CRM with web UI, SQLite database, contacts, sequences, email sending via Resend, and stats
- 2026-02-17: Added OpenClaw skill for bot integration
- 2026-02-17: Initial clone from `funcdude/crm-webhook` repo

## User Preferences
- Uses OpenClaw as their AI bot platform
