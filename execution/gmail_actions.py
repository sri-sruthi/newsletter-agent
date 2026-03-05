"""
Gmail Execution Layer

Actions:
    Filter discarded → archive + track sender memory
    HIGH score       → label 'High-Value'
    MEDIUM score     → label 'Medium-Value'
    LOW score        → archive
    Redundant        → archive
    3x discarded sender → unsubscribe
"""

from agents.email_agent import get_gmail_service
from memory.memory_manager import (
    record_discarded_senders,
    mark_as_unsubscribed,
    get_discard_summary,
    DISCARD_THRESHOLD,
)
from execution.unsubscribe_actions import execute_unsubscribes


def get_or_create_label(service, label_name: str) -> str:
    """Gets label ID by name, creates it if it doesn't exist."""
    existing = service.users().labels().list(userId='me').execute()
    for label in existing.get('labels', []):
        if label['name'].lower() == label_name.lower():
            return label['id']

    new_label = service.users().labels().create(
        userId='me',
        body={
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
    ).execute()
    print(f"  📌 Created Gmail label: '{label_name}'")
    return new_label['id']


def archive_email(service, email_id: str, subject: str):
    """Removes email from inbox, moves to All Mail."""
    try:
        service.users().messages().modify(
            userId='me',
            id=email_id,
            body={'removeLabelIds': ['INBOX']}
        ).execute()
        print(f"  📦 Archived: '{subject[:55]}'")
    except Exception as e:
        print(f"  ⚠️  Archive failed for '{subject[:40]}': {e}")


def label_email(service, email_id: str, label_ids: list, subject: str):
    """
    Applies labels to an email.
    Also removes conflicting value labels first to prevent double-labelling.
    label_ids is a list so we can apply one label at a time cleanly.
    """
    try:
        service.users().messages().modify(
            userId='me',
            id=email_id,
            body={'addLabelIds': label_ids}
        ).execute()
        print(f"  🏷️  Labelled: '{subject[:55]}'")
    except Exception as e:
        print(f"  ⚠️  Label failed for '{subject[:40]}': {e}")


def clear_value_labels(service, email_id: str, high_id: str, medium_id: str):
    """
    Removes both value labels before applying a new one.
    Prevents double-labelling from multiple runs.
    """
    try:
        service.users().messages().modify(
            userId='me',
            id=email_id,
            body={'removeLabelIds': [high_id, medium_id]}
        ).execute()
    except Exception:
        pass  # silently ignore — labels may not exist on this email
    
def mark_as_read(service, email_id: str, subject: str):
    """
    Marks an email as read by removing the UNREAD label.
    Used for archived/low/redundant emails you don't need to see.
    """
    try:
        service.users().messages().modify(
            userId='me',
            id=email_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
    except Exception as e:
        print(f"  ⚠️  Mark-read failed for '{subject[:40]}': {e}")


def execute_gmail_actions(
    high: list,
    medium: list,
    low: list,
    redundant: list,
    discarded: list
):
    service         = get_gmail_service()
    high_label_id   = get_or_create_label(service, "High-Value")
    medium_label_id = get_or_create_label(service, "Medium-Value")

    print("📬 Executing Gmail actions...\n")

    # ── Archive + mark READ: filtered-out emails ─────────────────
    if discarded:
        print(f"  🗑️  Archiving {len(discarded)} filtered-out emails:")
        for email in discarded:
            archive_email(service, email['id'], email['subject'])
            mark_as_read(service, email['id'], email['subject'])

    # ── Label HIGH — leave UNREAD so you see them ────────────────
    if high:
        print(f"\n  🟢 Labelling {len(high)} high-value emails:")
        for email in high:
            clear_value_labels(service, email['email_id'], high_label_id, medium_label_id)
            label_email(service, email['email_id'], [high_label_id], email['subject'])

    # ── Label MEDIUM — leave UNREAD so you see them ──────────────
    if medium:
        print(f"\n  🟡 Labelling {len(medium)} medium-value emails:")
        for email in medium:
            clear_value_labels(service, email['email_id'], high_label_id, medium_label_id)
            label_email(service, email['email_id'], [medium_label_id], email['subject'])

    # ── Archive + mark READ: low-value ───────────────────────────
    if low:
        print(f"\n  🔴 Archiving {len(low)} low-value emails:")
        for email in low:
            archive_email(service, email['email_id'], email['subject'])
            mark_as_read(service, email['email_id'], email['subject'])

    # ── Archive + mark READ: redundant ───────────────────────────
    if redundant:
        print(f"\n  🔁 Archiving {len(redundant)} redundant emails:")
        for email in redundant:
            archive_email(service, email['email_id'], email['subject'])
            mark_as_read(service, email['email_id'], email['subject'])

    # ── Memory tracking + Unsubscribe ────────────────────────────
    print(f"\n📝 Updating sender memory...\n")
    senders_to_unsub = record_discarded_senders(discarded)

    if senders_to_unsub:
        successfully_unsubscribed = execute_unsubscribes(senders_to_unsub)
        if successfully_unsubscribed:
            mark_as_unsubscribed(successfully_unsubscribed)
            print(f"\n  ✅ Unsubscribed from: {successfully_unsubscribed}")
        else:
            print("  ⚠️  Threshold reached, but no unsubscribe action succeeded this run")
    else:
        summary = get_discard_summary()
        tracking = summary.get("tracking", {})
        if tracking:
            top = sorted(
                tracking.items(),
                key=lambda item: item[1].get("count", 0),
                reverse=True
            )[:3]
            status = ", ".join(
                f"{v.get('name', k)} ({v.get('count', 0)}/{DISCARD_THRESHOLD})"
                for k, v in top
            )
            print(f"  ℹ️  No senders at threshold yet — closest: {status}")
        else:
            print("  ℹ️  No senders at threshold yet — tracking continues")

    print(f"\n✅ Gmail actions complete.\n")
