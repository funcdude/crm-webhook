#!/usr/bin/env python3
"""
CRM Webhook Receiver API client for OpenClaw.

Usage:
    python3 crm_api.py status
    python3 crm_api.py summary
    python3 crm_api.py events [--since-id N]
    python3 crm_api.py search [--type TYPE] [--resend-id ID] [--limit N]
    python3 crm_api.py clear
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = os.environ.get("CRM_WEBHOOK_URL", "").rstrip("/")
API_KEY = os.environ.get("CRM_API_KEY", "")


def make_request(path, method="GET"):
    url = f"{BASE_URL}{path}"
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"Error {e.code}: {err.get('error', body)}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        print("Is the webhook receiver running? Check your Replit project.", file=sys.stderr)
        sys.exit(1)


def cmd_status(_args):
    data = make_request("/")
    print(json.dumps(data, indent=2))


def cmd_summary(_args):
    data = make_request("/events/summary")
    print(f"Total events: {data['total_events']}")
    print()
    if data["by_type"]:
        print("Breakdown by type:")
        for event_type, count in sorted(data["by_type"].items(), key=lambda x: -x[1]):
            print(f"  {event_type}: {count}")
    else:
        print("No events recorded yet.")
    print()
    if data["recent_events"]:
        print(f"Last {len(data['recent_events'])} events:")
        for e in data["recent_events"]:
            print(f"  [{e['id']}] {e['type']} — {e.get('resend_id', 'N/A')} at {e['received_at']}")
    print()
    print(json.dumps(data, indent=2))


def cmd_events(args):
    path = "/events"
    if args.since_id:
        path += f"?since_id={args.since_id}"
    data = make_request(path)
    print(f"Found {data['count']} event(s) (latest_id: {data['latest_id']})")
    print()
    print(json.dumps(data, indent=2))


def cmd_search(args):
    params = {}
    if args.type:
        params["type"] = args.type
    if args.resend_id:
        params["resend_id"] = args.resend_id
    if args.limit:
        params["limit"] = str(args.limit)
    query = urllib.parse.urlencode(params)
    path = f"/events/search?{query}" if query else "/events/search"
    data = make_request(path)
    print(f"Found {data['count']} matching event(s)")
    print()
    print(json.dumps(data, indent=2))


def cmd_clear(_args):
    data = make_request("/events/clear", method="POST")
    print(f"Cleared {data.get('deleted', 0)} event(s)")
    print(json.dumps(data, indent=2))


def main():
    if not BASE_URL:
        print("Error: CRM_WEBHOOK_URL environment variable is not set.", file=sys.stderr)
        print("Set it to your webhook receiver URL (e.g., https://your-app.replit.app)", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="CRM Webhook Receiver API client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Check service health")
    subparsers.add_parser("summary", help="Get event summary with breakdown by type")

    events_parser = subparsers.add_parser("events", help="Fetch stored events")
    events_parser.add_argument("--since-id", type=int, help="Only return events with ID greater than this")

    search_parser = subparsers.add_parser("search", help="Search events by type or resend_id")
    search_parser.add_argument("--type", help="Filter by event type (delivered, bounced, opened, etc.)")
    search_parser.add_argument("--resend-id", help="Filter by Resend email ID")
    search_parser.add_argument("--limit", type=int, default=50, help="Max results to return (default: 50)")

    subparsers.add_parser("clear", help="Clear all stored events")

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "summary": cmd_summary,
        "events": cmd_events,
        "search": cmd_search,
        "clear": cmd_clear,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
