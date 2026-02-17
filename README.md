# SimpleCRM

A lightweight email outreach CRM with:
- Contact import from Hunter.io CSV
- Multi-step email sequences
- Automatic follow-ups (+3 days, +4 days)
- Open/click/reply tracking via Resend webhooks
- Auto-stop on reply or bounce

## Quick Start

1. **Import to Replit** from this GitHub repo
2. **Add Secrets** in Replit:
   - `RESEND_API_KEY` - Your Resend API key
   - `FROM_EMAIL` - e.g., `Oskar Hurme <oskar@oskarhurme.com>`
   - `REPLY_TO` - e.g., `oskar@oskarhurme.com`
   - `SECRET_KEY` - Random string for session security
3. **Run** - Click the Run button
4. **Configure Resend webhook** to POST to `https://your-app.repl.co/webhook`

## Resend Setup

### Domain Verification
1. Go to [resend.com](https://resend.com) → Domains
2. Add your domain (e.g., oskarhurme.com)
3. Add the DNS records Resend provides:
   - TXT record for SPF
   - TXT/CNAME for DKIM
4. Wait for verification

### Webhook Configuration
1. Go to Resend → Webhooks
2. Add endpoint: `https://your-replit-app.repl.co/webhook`
3. Select events:
   - `email.delivered`
   - `email.opened`
   - `email.clicked`
   - `email.bounced`
   - `email.received` (for reply detection)

## Usage

### Import Contacts
1. Go to Contacts → Import CSV
2. Upload your Hunter.io export
3. Add tags (e.g., "founders-q1")

### Create Sequence
1. Go to Sequences → New Sequence
2. Add steps:
   - Step 1: Delay 0 days (immediate)
   - Step 2: Delay 3 days
   - Step 3: Delay 4 days
3. Use variables: `{first_name}`, `{company}`, `{title}`

### Enroll & Send
1. In sequence, enroll contacts by tag
2. Go to Send to see queue
3. Click "Send All" to dispatch

### Monitor
- Dashboard shows recent activity
- Stats page shows open/reply rates
- Sequences stop automatically on reply

## Template Variables

Use in subject and body:
- `{first_name}` - First name or "there"
- `{last_name}` - Last name
- `{company}` - Company name or "your company"
- `{title}` - Job title
- `{email}` - Email address

## Architecture

```
Replit App
├── Web UI (Flask)
│   ├── /contacts    - Manage contacts
│   ├── /sequences   - Create email sequences
│   ├── /send        - Review and send queue
│   └── /stats       - View metrics
├── /webhook         - Receives Resend events
└── SQLite DB        - Stores everything
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESEND_API_KEY` | Yes | Your Resend API key |
| `FROM_EMAIL` | Yes | Sender email (must be verified domain) |
| `REPLY_TO` | No | Reply-to address (defaults to FROM_EMAIL) |
| `SECRET_KEY` | No | Flask session key (auto-generated if not set) |
| `RESEND_WEBHOOK_SECRET` | No | For webhook signature verification |
