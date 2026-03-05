from agents.email_agent import fetch_newsletters
from agents.filter_agent import filter_newsletters
from agents.content_agent import analyze_all_newsletters
from agents.redundancy_agent import detect_redundancy
from agents.scoring_agent import score_all_newsletters
from execution.gmail_actions import execute_gmail_actions

if __name__ == "__main__":

    # Phase 1 — Fetch
    print("📬 Fetching newsletters...\n")
    emails = fetch_newsletters(max_results=20)
    if not emails:
        print("📭 No unread emails found.")
        exit()

    # Filter — now returns (kept, discarded)
    print("🔎 Running Filter Agent...\n")
    relevant_emails, discarded_emails = filter_newsletters(emails)

    if not relevant_emails:
        print("📭 No relevant newsletters after filtering.")
        # Still archive the discarded ones
        if discarded_emails:
            from execution.gmail_actions import execute_gmail_actions
            execute_gmail_actions([], [], [], [], discarded_emails)
        exit()

    # Phase 2 — Analyze
    print("🧠 Running Content Intelligence Agent...\n")
    analyses = analyze_all_newsletters(relevant_emails)
    if not analyses:
        print("⚠️  No analyses returned.")
        exit()

    # Phase 3A — Redundancy
    print("🔁 Running Redundancy Agent...\n")
    unique_analyses, redundant = detect_redundancy(analyses)

    # Phase 3B — Scoring
    print("⭐ Running Scoring Agent...\n")
    high, medium, low = score_all_newsletters(unique_analyses)

    # Phase 3C — Act on Gmail (now passing discarded too)
    print("⚡ Executing Gmail Actions...\n")
    execute_gmail_actions(high, medium, low, redundant, discarded_emails)

    # Final Summary
    print("\n" + "="*60)
    print("📋 FINAL SUMMARY")
    print("="*60)
    for email in high:
        print(f"  🟢 HIGH    {email['final_score']}/10 | {email['subject'][:50]}")
    for email in medium:
        print(f"  🟡 MEDIUM  {email['final_score']}/10 | {email['subject'][:50]}")
    for email in low:
        print(f"  🔴 LOW     {email['final_score']}/10 | {email['subject'][:50]}")
    for email in redundant:
        print(f"  🔁 DUPL               | {email['subject'][:50]}")
    for email in discarded_emails:
        print(f"  🗑️  FILTERED           | {email['subject'][:50]}")