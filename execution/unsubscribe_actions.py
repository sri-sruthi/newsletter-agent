"""
Unsubscribe Execution Layer

Handles 3 types of unsubscribe mechanisms:

1. List-Unsubscribe header with One-Click POST (RFC 8058)
   → Fully automated, no browser needed

2. List-Unsubscribe header with mailto:
   → Sends an unsubscribe email automatically

3. Link in body → confirmation page
   → Opens in browser for manual confirmation
   → We can't automate this without a full browser automation tool
      (that would require selenium/playwright — overkill for now)
"""

import re
import requests
import webbrowser
from agents.email_agent import get_gmail_service


# ── Unsubscribe link patterns for body scanning ─────────────────────────────
UNSUB_PATTERNS = [
    r'https?://[^\s<>"\']+unsubscribe[^\s<>"\']*',
    r'https?://[^\s<>"\']+optout[^\s<>"\']*',
    r'https?://[^\s<>"\']+opt-out[^\s<>"\']*',
    r'https?://[^\s<>"\']+email[^\s<>"\']*remove[^\s<>"\']*',
]


def get_full_email_data(service, sender_address: str):
    """
    Fetches the most recent email from a sender.
    Returns full message data including headers + body.
    """
    import base64

    try:
        results = service.users().messages().list(
            userId='me',
            q=f'from:{sender_address}',
            maxResults=1
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            return None, None

        msg_data = service.users().messages().get(
            userId='me',
            id=messages[0]['id'],
            format='full'
        ).execute()

        headers = msg_data['payload']['headers']
        payload = msg_data['payload']

        # Extract List-Unsubscribe header if present
        unsub_header = next(
            (h['value'] for h in headers
             if h['name'].lower() == 'list-unsubscribe'),
            None
        )

        # Extract List-Unsubscribe-Post header (one-click indicator)
        unsub_post = next(
            (h['value'] for h in headers
             if h['name'].lower() == 'list-unsubscribe-post'),
            None
        )

        # Extract body
        def extract_body(p):
            if 'parts' in p:
                for part in p['parts']:
                    if part['mimeType'] in ('text/plain', 'text/html'):
                        data = part['body'].get('data', '')
                        if data:
                            return base64.urlsafe_b64decode(data).decode(
                                'utf-8', errors='ignore'
                            )
            else:
                data = p['body'].get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode(
                        'utf-8', errors='ignore'
                    )
            return ""

        body = extract_body(payload)

        return {
            'unsub_header': unsub_header,
            'unsub_post':   unsub_post,
            'body':         body
        }, messages[0]['id']

    except Exception as e:
        print(f"    ⚠️  Could not fetch email for {sender_address}: {e}")
        return None, None


def try_one_click_unsubscribe(url: str) -> bool:
    """
    RFC 8058 one-click unsubscribe — sends POST request.
    Fully automated, no browser needed.
    """
    try:
        response = requests.post(
            url,
            data={'List-Unsubscribe': 'One-Click'},
            headers={'User-Agent': 'Mozilla/5.0 (compatible; newsletter-agent/1.0)'},
            timeout=10
        )
        return response.status_code < 400
    except Exception as e:
        print(f"    ⚠️  One-click POST failed: {e}")
        return False


def try_mailto_unsubscribe(mailto: str, gmail_service) -> bool:
    """
    Sends an unsubscribe email to the mailto address.
    Fully automated.
    """
    import base64
    from email.mime.text import MIMEText

    try:
        # Extract address from mailto:something@domain.com
        address = mailto.replace('mailto:', '').split('?')[0].strip()

        msg = MIMEText('Please unsubscribe me from this mailing list.')
        msg['To']      = address
        msg['Subject'] = 'Unsubscribe'

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        gmail_service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()

        print(f"    ✉️  Sent unsubscribe email to: {address}")
        return True

    except Exception as e:
        print(f"    ⚠️  Mailto unsubscribe failed: {e}")
        return False


def parse_list_unsubscribe_header(header_value: str) -> dict:
    """
    Parses List-Unsubscribe header value.

    Header can contain:
        <https://...>, <mailto:...>
        or just one of them

    Returns dict with 'url' and/or 'mailto' keys.
    """
    result  = {}
    entries = re.findall(r'<([^>]+)>', header_value)

    for entry in entries:
        if entry.startswith('mailto:'):
            result['mailto'] = entry
        elif entry.startswith('http'):
            result['url'] = entry

    return result


def find_body_unsubscribe_link(body: str) -> str | None:
    """
    Fallback: scan email body for unsubscribe link.
    """
    for pattern in UNSUB_PATTERNS:
        matches = re.findall(pattern, body, re.IGNORECASE)
        if matches:
            return matches[0].rstrip('.,;)')
    return None


def execute_unsubscribes(senders_to_unsub: dict) -> list:
    """
    Main unsubscribe execution.

    Tries methods in order of automation level:
      1. One-click POST (fully automated)
      2. Mailto (fully automated)
      3. Body link → open in browser (requires your click to confirm)

    Returns list of addresses considered handled.
    """
    if not senders_to_unsub:
        return []

    service      = get_gmail_service()
    handled      = []
    needs_manual = []

    print(f"\n🚫 Processing unsubscribes for {len(senders_to_unsub)} senders...\n")

    for address, info in senders_to_unsub.items():
        name  = info.get('name', address)
        count = info.get('count', 0)

        print(f"  📧 {name} ({address}) — discarded {count} times")

        email_data, _ = get_full_email_data(service, address)

        if not email_data:
            print(f"    ⚠️  Could not retrieve email — skipping\n")
            continue

        unsub_header = email_data.get('unsub_header')
        unsub_post   = email_data.get('unsub_post')
        body         = email_data.get('body', '')

        # ── Method 1: One-click POST ─────────────────────────────
        if unsub_header and unsub_post:
            parsed = parse_list_unsubscribe_header(unsub_header)
            if 'url' in parsed:
                print(f"    🤖 Trying one-click unsubscribe (RFC 8058)...")
                success = try_one_click_unsubscribe(parsed['url'])
                if success:
                    print(f"    ✅ One-click unsubscribe successful — fully automated")
                    handled.append(address)
                    print()
                    continue

        # ── Method 2: Mailto ────────────────────────────────────
        if unsub_header:
            parsed = parse_list_unsubscribe_header(unsub_header)
            if 'mailto' in parsed:
                print(f"    ✉️  Trying mailto unsubscribe...")
                success = try_mailto_unsubscribe(parsed['mailto'], service)
                if success:
                    print(f"    ✅ Unsubscribe email sent — fully automated")
                    handled.append(address)
                    print()
                    continue

        # ── Method 3: Body link → open browser ──────────────────
        link = None
        if unsub_header:
            parsed = parse_list_unsubscribe_header(unsub_header)
            link   = parsed.get('url')

        if not link:
            link = find_body_unsubscribe_link(body)

        if link:
            print(f"    🌐 Confirmation page required — opening in browser")
            print(f"    🔗 {link[:80]}")
            print(f"    👆 Please click confirm on the page that opens")
            webbrowser.open(link)
            needs_manual.append({'name': name, 'address': address, 'link': link})
            handled.append(address)  # mark as handled even if manual
            print()
            continue

        print(f"    ❌ No unsubscribe method found — will try again next run\n")

    # Summary of anything that needed manual confirmation
    if needs_manual:
        print(f"\n  ⚠️  {len(needs_manual)} sender(s) opened in browser for confirmation:")
        for item in needs_manual:
            print(f"     → {item['name']} — please confirm on the page")
        print()

    return handled