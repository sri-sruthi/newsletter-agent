"""
Memory Manager

Handles persistent memory across agent runs.
Tracks how many times each sender has been discarded.
Used by gmail_actions to decide when to unsubscribe.
"""

import json
import os
import re

MEMORY_PATH        = "memory/history.json"
try:
    DISCARD_THRESHOLD = max(1, int(os.getenv("DISCARD_THRESHOLD", "3")))
except ValueError:
    DISCARD_THRESHOLD = 3


# ── Trusted senders — never unsubscribe, never penalise ─────────────────────
# Add any sender address here that you want to permanently protect.
# Even if their individual emails get discarded (off-topic issues etc),
# they will never be unsubscribed and their discard count won't be tracked.
#
# Rule of thumb: add newsletters you CHOSE to subscribe to and want to keep
# even if some issues are irrelevant.

WHITELISTED_SENDERS = {
    # Science / Research
    "briefing@nature.com",           # Nature Briefing
    "marketing@statnews.com",        # STAT News — mix of science and tech
    # Tech newsletters you trust
    "newsletter@tldr.tech",          # TLDR
    "dan@tldrnewsletter.com",        # TLDR- all editions
    "hello@deeplearning.ai",         # DeepLearning.AI
    "hi@mail.beehiiv.com",           # common Beehiiv sender
    "hi@news.jayshetty.me",
    "newsletter@towardsdatascience.com",
    "newsletter@email.businessinsider.com",
    "dailydozen@email.forbes.com",
    "info@dailystoic.com",
    # Add more as you discover them:
    # "sender@domain.com",
}


def load_memory() -> dict:
    try:
        with open(MEMORY_PATH, 'r') as f:
            data = json.load(f)
            if "sender_discard_counts" not in data:
                data["sender_discard_counts"] = {}
            if "unsubscribed_senders" not in data:
                data["unsubscribed_senders"] = []
            if "whitelisted_senders" not in data:
                data["whitelisted_senders"] = []
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        return {
            "sender_discard_counts": {},
            "unsubscribed_senders":  [],
            "whitelisted_senders":   []
        }


def save_memory(memory: dict):
    os.makedirs("memory", exist_ok=True)
    with open(MEMORY_PATH, 'w') as f:
        json.dump(memory, f, indent=2)


def extract_email_address(sender_string: str) -> str:
    match = re.search(r'<(.+?)>', sender_string)
    if match:
        return match.group(1).lower().strip()
    return sender_string.lower().strip()


def extract_sender_name(sender_string: str) -> str:
    match = re.match(r'^(.+?)\s*<', sender_string)
    if match:
        return match.group(1).strip()
    return sender_string.strip()


def is_whitelisted(address: str) -> bool:
    """
    Checks both the hardcoded whitelist above AND
    any addresses the user has manually added to history.json.
    """
    if address in WHITELISTED_SENDERS:
        return True
    memory = load_memory()
    return address in memory.get("whitelisted_senders", [])


def add_to_whitelist(address: str, name: str = ""):
    """
    Adds a sender to the persistent whitelist in history.json.
    Also removes them from discard_counts if tracked.
    """
    memory = load_memory()

    if address not in memory["whitelisted_senders"]:
        memory["whitelisted_senders"].append(address)

    # Remove from discard tracking — fresh start
    memory["sender_discard_counts"].pop(address, None)

    save_memory(memory)
    print(f"  ✅ Whitelisted: {name or address}")


def record_discarded_senders(discarded_emails: list) -> dict:
    """
    Records each discarded email's sender in memory.
    Skips whitelisted senders entirely.
    Returns senders that have hit the threshold this run.
    """
    memory   = load_memory()
    counts   = memory["sender_discard_counts"]
    already  = set(memory["unsubscribed_senders"])
    to_unsub = {}

    for email in discarded_emails:
        raw_sender = email.get('sender', 'unknown')
        address    = extract_email_address(raw_sender)
        name       = extract_sender_name(raw_sender)

        # Skip already unsubscribed — no output needed
        if address in already:
            continue

        # Skip whitelisted senders — never penalise them
        if is_whitelisted(address):
            print(f"  🛡️  Whitelisted — skipping: '{name}'")
            continue

        if address not in counts:
            counts[address] = {"count": 0, "name": name}
        counts[address]["count"] += 1

        print(f"  📝 Recorded discard: '{name}' ({address}) "
              f"— {counts[address]['count']}/{DISCARD_THRESHOLD} strikes")

        if counts[address]["count"] >= DISCARD_THRESHOLD:
            to_unsub[address] = counts[address]

    memory["sender_discard_counts"] = counts
    save_memory(memory)
    return to_unsub


def mark_as_unsubscribed(sender_addresses: list):
    memory = load_memory()
    for address in sender_addresses:
        if address not in memory["unsubscribed_senders"]:
            memory["unsubscribed_senders"].append(address)
        memory["sender_discard_counts"].pop(address, None)
    save_memory(memory)


def get_discard_summary() -> dict:
    memory = load_memory()
    return {
        "tracking":     memory["sender_discard_counts"],
        "unsubscribed": memory["unsubscribed_senders"],
        "whitelisted":  memory.get("whitelisted_senders", [])
    }
