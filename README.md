# CRM Webhook Receiver

Simple Flask webhook receiver for Resend email events. Stores events for a local CRM to fetch.

## Deploy to Replit

1. Import this repo to Replit
2. Add Secrets:
   - `WEBHOOK_API_KEY` - API key for auth (generate something random)
   - `RESEND_WEBHOOK_SECRET` - (optional) from Resend dashboard for signature verification
3. Click Run

## Endpoints

- `GET /` - Health check
- `POST /webhook` - Receives Resend webhook events
- `GET /events?since_id=0` - Fetch stored events (for local CRM)
- `POST /events/clear` - Clear all events

## Configure Resend

In Resend Dashboard → Webhooks:
- **Endpoint:** `https://your-repl.repl.co/webhook`
- **Events:** delivered, opened, clicked, bounced, received
