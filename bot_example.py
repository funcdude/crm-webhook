"""
SimpleCRM Bot Example — Python
Shows how to connect your bot to the CRM API.

Usage:
    1. Set your CRM URL and API key below
    2. Run: python bot_example.py
"""

import requests

CRM_URL = "https://your-repl-url.replit.app"  # Replace with your deployed CRM URL
API_KEY = "your-api-key-here"                  # Replace with your CRM_API_KEY

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def check_health():
    r = requests.get(f"{CRM_URL}/api/health")
    print("Health:", r.json())


def add_contact(email, first_name="", last_name="", company="", title="", tags=""):
    r = requests.post(f"{CRM_URL}/api/contacts", headers=HEADERS, json={
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "company": company,
        "title": title,
        "tags": tags,
        "source": "bot"
    })
    data = r.json()
    if r.ok:
        action = "Created" if data.get("created") else "Updated"
        print(f"{action} contact: {data['contact']['email']} (id={data['contact']['id']})")
    else:
        print(f"Error: {data}")
    return data


def add_contacts_bulk(contacts_list):
    r = requests.post(f"{CRM_URL}/api/contacts/bulk", headers=HEADERS, json={
        "contacts": contacts_list
    })
    data = r.json()
    print(f"Bulk import: {data.get('created')} created, {data.get('updated')} updated")
    if data.get("errors"):
        print(f"  Errors: {data['errors']}")
    return data


def list_contacts(search="", tag="", limit=10):
    params = {"limit": limit}
    if search:
        params["search"] = search
    if tag:
        params["tag"] = tag
    r = requests.get(f"{CRM_URL}/api/contacts", headers=HEADERS, params=params)
    data = r.json()
    print(f"Found {data['total']} contacts:")
    for c in data["contacts"]:
        print(f"  [{c['id']}] {c['first_name']} {c['last_name']} <{c['email']}> ({c.get('company','')})")
    return data


def get_contact(contact_id):
    r = requests.get(f"{CRM_URL}/api/contacts/{contact_id}", headers=HEADERS)
    return r.json()


def list_sequences():
    r = requests.get(f"{CRM_URL}/api/sequences", headers=HEADERS)
    data = r.json()
    print("Available sequences:")
    for s in data["sequences"]:
        print(f"  [{s['id']}] {s['name']} — {s['step_count']} steps, {s['enrolled_contacts']} active")
    return data


def enroll_in_sequence(sequence_id, contact_id=None, email=None):
    payload = {}
    if contact_id:
        payload["contact_id"] = contact_id
    if email:
        payload["email"] = email
    r = requests.post(f"{CRM_URL}/api/sequences/{sequence_id}/enroll", headers=HEADERS, json=payload)
    data = r.json()
    if r.ok:
        print(f"Enrolled contact in sequence {sequence_id}: {data}")
    else:
        print(f"Enroll error: {data}")
    return data


def enroll_bulk(sequence_id, contact_ids):
    r = requests.post(
        f"{CRM_URL}/api/sequences/{sequence_id}/enroll/bulk",
        headers=HEADERS,
        json={"contact_ids": contact_ids}
    )
    data = r.json()
    print(f"Bulk enroll: {data.get('enrolled')} enrolled, {data.get('skipped')} skipped")
    return data


def check_contact_sequences(contact_id):
    r = requests.get(f"{CRM_URL}/api/contacts/{contact_id}/sequences", headers=HEADERS)
    data = r.json()
    if r.ok:
        print(f"Sequences for {data['contact']['email']}:")
        for s in data["sequences"]:
            print(f"  {s['sequence_name']}: step {s['current_step']}/{s['total_steps']} — {s['status']}")
    return data


def stop_sequence(contact_id, sequence_id):
    r = requests.post(
        f"{CRM_URL}/api/contacts/{contact_id}/sequences/{sequence_id}/stop",
        headers=HEADERS
    )
    data = r.json()
    print(f"Stop result: {data}")
    return data


if __name__ == "__main__":
    print("=== SimpleCRM Bot Example ===\n")

    print("1. Health check")
    check_health()

    print("\n2. Add a contact")
    add_contact("jane@example.com", first_name="Jane", last_name="Doe", company="Acme Inc")

    print("\n3. List contacts")
    list_contacts()

    print("\n4. List sequences")
    list_sequences()

    print("\n--- Done! Modify this script for your bot's needs. ---")
