"""
Email Agent

Handles Gmail OAuth2. On Railway, token is loaded from
GOOGLE_TOKEN_JSON environment variable instead of token.json file.
This avoids the browser popup problem on headless servers.
"""

import os
import json
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/documents",
]


def get_gmail_service():
    return _get_google_service("gmail", "v1")


def get_docs_service():
    return _get_google_service("docs", "v1")


def _get_google_service(api: str, version: str):
    """
    Builds a Google API service client.

    Token loading priority:
    1. GOOGLE_TOKEN_JSON env var (Railway/production)
    2. token.json file (local development)

    This means local dev still works exactly as before,
    but Railway uses the env var — no browser needed.
    """
    creds = None

    # Production: load from environment variable
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        token_data = json.loads(token_env)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Local dev: load from file
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token back
        if token_env:
            # On Railway — can't save to file, but refreshed creds
            # stay valid in memory for this run.
            pass
        else:
            with open("token.json", "w") as f:
                f.write(creds.to_json())

    # First-time setup (local only)
    if not creds or not creds.valid:
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())

    return build(api, version, credentials=creds)


def fetch_newsletters(max_results=20):
    """
    Fetches unread emails from Gmail inbox.
    Returns a list of dicts with sender, subject, body, date.
    """
    service = get_gmail_service()

    # Search unread inbox emails that were not already processed by labels
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        q="is:unread -label:High-Value -label:Medium-Value",
        maxResults=max_results,
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        print("📭 No new unprocessed emails found.")
        return []

    newsletters = []

    for msg in messages:
        # Each message only gives us an ID — we fetch full details next
        msg_data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full",
        ).execute()

        headers = msg_data["payload"]["headers"]

        # Extract subject, sender, date from headers
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown")

        # Extract email body (it's base64 encoded)
        body = extract_body(msg_data["payload"])

        newsletters.append(
            {
                "id": msg["id"],  # needed later for archiving/labeling
                "sender": sender,
                "subject": subject,
                "body": body,
                "date": date,
            }
        )

    print(f"✅ Fetched {len(newsletters)} unread emails.")
    return newsletters


def extract_body(payload):
    """
    Gmail stores email body in base64.
    This function finds and decodes it.
    """
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                break
    else:
        data = payload["body"].get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return body[:3000]  # limit to 3000 chars to save model tokens later
