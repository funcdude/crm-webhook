# CRM Webhook Receiver

## Overview
A lightweight Flask-based webhook receiver that captures email event data from Resend and stores it in memory for a local CRM system to poll and retrieve. The service acts as a bridge between Resend's email event notifications and an external CRM application. Includes a ready-to-use OpenClaw skill for bot-driven access to the API.

## Current State
- Fully functional webhook receiver running on port 5000
- In-memory event storage (resets when the app restarts)
- API key authentication for event retrieval and admin endpoints
- OpenClaw skill for bot integration included in `openclaw-skill/`

## Tech Stack
- **Language:** Python 3.11
- **Web Framework:** Flask (>=2.0.0, currently installed 3.1.2)
- **WSGI Server:** Gunicorn (>=20.0.0, available for production use)
- **Storage:** In-memory list (no database)
- **Port:** Configurable via `PORT` env var, defaults to 5000

## Project Structure
```
.
├── main.py                          # Flask application with all endpoints
├── requirements.txt                 # Python dependencies (flask, gunicorn)
├── .gitignore                       # Git ignore rules
├── README.md                        # Original project README
├── replit.md                        # This file
└── openclaw-skill/                  # OpenClaw bot skill
    ├── SKILL.md                     # Skill definition and instructions for OpenClaw
    └── scripts/
        └── crm_api.py               # Python CLI client for the webhook API
```

## API Endpoints
| Method | Path              | Description                                              | Auth Required |
|--------|-------------------|----------------------------------------------------------|---------------|
| GET    | `/`               | Health check, returns service status and event count     | No            |
| POST   | `/webhook`        | Receives webhook events from Resend                      | Signature (optional) |
| GET    | `/events`         | Fetch stored events, supports `?since_id=N` filtering    | API Key       |
| GET    | `/events/summary` | Aggregated event summary with breakdown by type and recent events | API Key |
| GET    | `/events/search`  | Search events by `?type=` and/or `?resend_id=` with `?limit=N` | API Key  |
| POST   | `/events/clear`   | Clear all stored events                                  | API Key       |

## Environment Variables / Secrets
| Variable                | Purpose                                         | Required |
|-------------------------|-------------------------------------------------|----------|
| `WEBHOOK_API_KEY`       | API key for authenticating event fetch/clear requests | Recommended |
| `RESEND_WEBHOOK_SECRET` | Resend webhook signing secret for signature verification | Optional |

## Key Behaviors
- Events are stored in an in-memory list, capped at 10,000 entries (oldest are dropped)
- Webhook signature verification via HMAC-SHA256 is supported but optional
- The `/events` endpoint supports incremental polling via the `since_id` query parameter
- API key auth is skipped if `WEBHOOK_API_KEY` is left as the default placeholder
- `/events/summary` returns total counts, breakdown by event type, and the 10 most recent events
- `/events/search` supports filtering by event type and Resend email ID with configurable result limits

## OpenClaw Skill
The `openclaw-skill/` directory contains a ready-to-use OpenClaw skill that lets a bot interact with this webhook receiver. To use it:

1. Copy the `openclaw-skill/` folder to your OpenClaw skills directory (e.g., `~/.openclaw/skills/crm-webhook/`)
2. Set environment variables in your OpenClaw config:
   - `CRM_WEBHOOK_URL` — base URL of this webhook receiver
   - `CRM_API_KEY` — the same value as `WEBHOOK_API_KEY`
3. The bot can then check email events, search for bounces, get summaries, etc.

The skill's `scripts/crm_api.py` supports these commands:
- `status` — health check
- `summary` — aggregated event overview
- `events [--since-id N]` — fetch events
- `search [--type TYPE] [--resend-id ID] [--limit N]` — search events
- `clear` — clear all events

## Recent Changes
- 2026-02-17: Added `/events/summary` and `/events/search` endpoints for bot-friendly data access
- 2026-02-17: Created OpenClaw skill with SKILL.md and crm_api.py CLI client
- 2026-02-17: Cloned from `funcdude/crm-webhook` repo and set up on Replit

## User Preferences
- Uses OpenClaw as their AI bot platform
