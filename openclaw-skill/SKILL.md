---
name: crm-webhook
description: Check email events, view bounces, see delivery status, search Resend webhook events, get CRM email summary
emoji: 📧
metadata:
  openclaw:
    requires:
      bins: ["python3", "curl"]
      env: ["CRM_WEBHOOK_URL", "CRM_API_KEY"]
    primaryEnv: "CRM_API_KEY"
    skillKey: "crm-webhook"
---

# CRM Webhook Receiver

Connects to the CRM Webhook Receiver API to check email event data from Resend. Use this skill to monitor email deliveries, bounces, opens, clicks, and other email events captured by the webhook receiver.

## When to Use

- "Check email events"
- "Any new bounces?"
- "Show me recent email activity"
- "How many emails were delivered today?"
- "Search for events for email ID xyz"
- "Get email summary"
- "Clear all email events"
- "What's the email delivery status?"
- "Show bounced emails"
- "Any new webhook events?"

## Configuration

The following environment variables must be set in your OpenClaw config:

- `CRM_WEBHOOK_URL` — The base URL of the webhook receiver (e.g., `https://your-app.replit.app`)
- `CRM_API_KEY` — The API key for authenticating requests

## Instructions

### Get a quick summary of all events

Run: `exec python3 <skill_path>/scripts/crm_api.py summary`

This returns the total event count, breakdown by type (delivered, bounced, opened, clicked, etc.), and the 10 most recent events.

### Fetch all events (or new events since a given ID)

Run: `exec python3 <skill_path>/scripts/crm_api.py events`

To get only events newer than a specific ID:

Run: `exec python3 <skill_path>/scripts/crm_api.py events --since-id 42`

### Search for specific events

By event type (use the full Resend event name like `email.delivered`, `email.bounced`, `email.opened`, `email.clicked`, `email.complained`):

Run: `exec python3 <skill_path>/scripts/crm_api.py search --type email.bounced`

By Resend email ID:

Run: `exec python3 <skill_path>/scripts/crm_api.py search --resend-id abc123`

Limit number of results:

Run: `exec python3 <skill_path>/scripts/crm_api.py search --type delivered --limit 5`

### Check service health

Run: `exec python3 <skill_path>/scripts/crm_api.py status`

### Clear all events (use with caution)

Run: `exec python3 <skill_path>/scripts/crm_api.py clear`

Only do this if the user explicitly asks to clear or reset events. Confirm with the user before running.

## Interpreting Results

- **email.delivered** — Email was successfully delivered to the recipient's mail server
- **email.bounced** — Email could not be delivered (check the data for bounce reason)
- **email.opened** — Recipient opened the email
- **email.clicked** — Recipient clicked a link in the email
- **email.complained** — Recipient marked the email as spam
- **email.unsubscribed** — Recipient unsubscribed

When the user asks about problems or issues, focus on **bounced** and **complained** events and highlight the affected email addresses and reasons.

## Error Handling

- If `CRM_WEBHOOK_URL` or `CRM_API_KEY` is not set, tell the user to configure them in their OpenClaw settings
- If the API returns a 401 error, the API key is incorrect
- If the API is unreachable, the webhook receiver may not be running — suggest the user check their Replit project
- If there are 0 events, the webhook receiver hasn't received any events yet — suggest checking the Resend webhook configuration

## Examples

**User:** "Any email bounces?"
**Action:** Run search with `--type bounced`, then summarize results showing affected email addresses and bounce reasons.

**User:** "Show me what happened today"
**Action:** Run summary to get an overview, then present the breakdown by type and list recent events.

**User:** "Look up events for email abc-123"
**Action:** Run search with `--resend-id abc-123` and present all matching events chronologically.
