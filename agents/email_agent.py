import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# This defines what permissions we're asking Gmail for
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify'  # read + archive + label
]

def get_gmail_service():
    """
    Handles OAuth2 authentication with Gmail.
    First run: opens browser for you to log in.
    After that: uses saved token.json automatically.
    """
    creds = None

    # If token already exists from a previous login, load it
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials, ask user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # silently refresh expired token
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)  # opens browser

        # Save the token for next time (no browser needed again)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def fetch_newsletters(max_results=20):
    """
    Fetches unread emails from Gmail inbox.
    Returns a list of dicts with sender, subject, body, date.
    """
    service = get_gmail_service()

    # Search for unread emails (you can later filter by label/sender)
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        q='is:unread',
        maxResults=max_results
    ).execute()

    messages = results.get('messages', [])
    newsletters = []

    for msg in messages:
        # Each message only gives us an ID — we fetch full details next
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        headers = msg_data['payload']['headers']

        # Extract subject, sender, date from headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender  = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date    = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

        # Extract email body (it's base64 encoded)
        body = extract_body(msg_data['payload'])

        newsletters.append({
            'id': msg['id'],         # needed later for archiving/labeling
            'sender': sender,
            'subject': subject,
            'body': body,
            'date': date
        })

    print(f"✅ Fetched {len(newsletters)} unread emails.")
    return newsletters


def extract_body(payload):
    """
    Gmail stores email body in base64.
    This function finds and decodes it.
    """
    body = ""

    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                break
    else:
        data = payload['body'].get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

    return body[:3000]  # limit to 3000 chars to save OpenAI tokens later