"""
Resend Webhook Receiver for Replit

This receives webhook events from Resend and stores them for the local CRM to fetch.

Deploy this on Replit and configure the URL in Resend's webhook settings.
"""
import os
import json
import hmac
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
API_KEY = os.environ.get('WEBHOOK_API_KEY', 'change-me-in-secrets')
RESEND_WEBHOOK_SECRET = os.environ.get('RESEND_WEBHOOK_SECRET', '')

# In-memory storage (persists while Replit is running)
# For production, use Replit's built-in database or SQLite
events = []
event_id_counter = 0

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Resend webhook signature."""
    if not RESEND_WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    
    expected = hmac.new(
        RESEND_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected}", signature)

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'service': 'CRM Webhook Receiver',
        'events_stored': len(events)
    })

@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """Receive webhook events from Resend."""
    global event_id_counter
    
    # Verify signature if configured
    signature = request.headers.get('svix-signature', '')
    if RESEND_WEBHOOK_SECRET and not verify_webhook_signature(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        data = request.json
        
        # Extract relevant info
        event_type = data.get('type', 'unknown')
        resend_id = data.get('data', {}).get('email_id') or data.get('data', {}).get('id')
        
        # Store the event
        event_id_counter += 1
        event = {
            'id': event_id_counter,
            'type': event_type,
            'resend_id': resend_id,
            'data': data.get('data', {}),
            'received_at': datetime.utcnow().isoformat()
        }
        events.append(event)
        
        print(f"📥 Received: {event_type} for {resend_id}")
        
        # Keep only last 10000 events to prevent memory issues
        if len(events) > 10000:
            events.pop(0)
        
        return jsonify({'status': 'ok', 'event_id': event_id_counter})
        
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/events', methods=['GET'])
def get_events():
    """Fetch stored events (called by local CRM)."""
    # Optional API key check
    api_key = request.headers.get('X-API-Key', '')
    if API_KEY and API_KEY != 'change-me-in-secrets' and api_key != API_KEY:
        return jsonify({'error': 'Invalid API key'}), 401
    
    since_id = request.args.get('since_id', 0, type=int)
    
    # Return events with ID > since_id
    filtered = [e for e in events if e['id'] > since_id]
    
    return jsonify({
        'events': filtered,
        'count': len(filtered),
        'latest_id': events[-1]['id'] if events else 0
    })

@app.route('/events/clear', methods=['POST'])
def clear_events():
    """Clear all stored events (admin function)."""
    api_key = request.headers.get('X-API-Key', '')
    if API_KEY and API_KEY != 'change-me-in-secrets' and api_key != API_KEY:
        return jsonify({'error': 'Invalid API key'}), 401
    
    global events, event_id_counter
    count = len(events)
    events = []
    event_id_counter = 0
    
    return jsonify({'status': 'cleared', 'deleted': count})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Webhook receiver starting on port {port}")
    print(f"   Configure Resend to POST to: https://your-replit-url.repl.co/webhook")
    app.run(host='0.0.0.0', port=port)
