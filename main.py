from agents.email_agent import fetch_newsletters
from agents.filter_agent import filter_newsletters
from agents.content_agent import analyze_all_newsletters

if __name__ == "__main__":

    # Phase 1 — Fetch emails
    print("📬 Fetching newsletters...\n")
    emails = fetch_newsletters(max_results=20)

    if not emails:
        print("📭 No unread emails found.")
        exit()

    # Filter — remove junk before wasting API calls
    print("🔎 Running Filter Agent...\n")
    relevant_emails = filter_newsletters(emails)

    if not relevant_emails:
        print("📭 No relevant newsletters found after filtering. Done.")
        exit()

    # Phase 2 — Analyze only what passed the filter
    print("🧠 Running Content Intelligence Agent...\n")
    analyses = analyze_all_newsletters(relevant_emails)

    if not analyses:
        print("⚠️  No analyses returned. Done.")
        exit()

    # Print results
    for a in analyses:
        print(f"\n{'='*60}")
        print(f"📧 {a['subject']}")
        print(f"📝 Summary: {a['summary']}")
        print(f"🏷️  Topics:  {a['topics']}")
        print(f"🔧 Tools:   {a['tools']}")
        print(f"💡 Skills:  {a['skills']}")