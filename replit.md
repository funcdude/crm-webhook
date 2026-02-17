# CRM Webhook Receiver

## Overview
A lightweight Flask-based webhook receiver that captures email event data from Resend and stores it in memory for a local CRM system to poll and retrieve. The service acts as a bridge between Resend's email event notifications and an external CRM application.

## Current State
- Fully functional webhook receiver running on port 5000
- In-memory event storage (resets when the app restarts)
- API key authentication for event retrieval and admin endpoints

## Tech Stack
- **Language:** Python 3.11
- **Web Framework:** Flask (>=2.0.0, currently installed 3.1.2)
- **WSGI Server:** Gunicorn (>=20.0.0, available for production use)
- **Storage:** In-memory list (no database)
- **Port:** Configurable via `PORT` env var, defaults to 5000

## Project Structure
```
.
├── main.py              # Flask application with all endpoints
├── requirements.txt     # Python dependencies (flask, gunicorn)
├── .gitignore           # Git ignore rules
├── README.md            # Original project README
└── replit.md            # This file
```

## API Endpoints
| Method | Path             | Description                                      | Auth Required |
|--------|------------------|--------------------------------------------------|---------------|
| GET    | `/`              | Health check, returns service status and event count | No          |
| POST   | `/webhook`       | Receives webhook events from Resend              | Signature (optional) |
| GET    | `/events`        | Fetch stored events, supports `?since_id=N` filtering | API Key    |
| POST   | `/events/clear`  | Clear all stored events                          | API Key       |

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

## Recent Changes
- 2026-02-17: Cloned from `funcdude/crm-webhook` repo and set up on Replit

## User Preferences
- (To be updated as preferences are expressed)
