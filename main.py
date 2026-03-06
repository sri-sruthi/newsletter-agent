from agents.email_agent import fetch_newsletters
from agents.filter_agent import filter_newsletters
from agents.content_agent import analyze_all_newsletters
from agents.redundancy_agent import detect_redundancy
from agents.scoring_agent import score_all_newsletters
from agents.github_agent import extract_github_skills
from agents.skill_gap_agent import run_skill_gap_analysis
from execution.gmail_actions import execute_gmail_actions
from execution.notion_actions import store_to_notion
from execution.docs_actions import update_google_doc
from config import GOOGLE_DOC_ID


def print_skill_gap_summary(skill_gap_report: dict):
    gaps = skill_gap_report.get("skill_gaps", [])
    projects = skill_gap_report.get("project_ideas", [])

    print(f"\n🎯 Skill gaps: {len(gaps)}")
    for i, gap in enumerate(gaps, 1):
        print(f"  {i}. [{gap.get('priority', 'MEDIUM')}] {gap.get('skill', 'Unknown')}")

    print(f"\n💡 Projects:   {len(projects)}")
    for i, project in enumerate(projects, 1):
        title = project.get("title", "Untitled")
        eta = project.get("estimated_time", "?")
        print(f"  {i}. {title} ({eta})")


if __name__ == "__main__":

    # Phase 1 — Fetch
    print("📬 Fetching newsletters...\n")
    emails = fetch_newsletters(max_results=20)
    if not emails:
        print("📭 No unread emails found.")
        exit()

    # Filter
    print("🔎 Running Filter Agent...\n")
    relevant_emails, discarded_emails = filter_newsletters(emails)
    if not relevant_emails:
        print("📭 No relevant newsletters after filtering.")
        if discarded_emails:
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

    # Phase 3C — Gmail Actions
    print("⚡ Executing Gmail Actions...\n")
    execute_gmail_actions(high, medium, low, redundant, discarded_emails)

    # Phase 4A — GitHub Skills
    print("\n🐙 Running GitHub Agent...\n")
    github_skills = extract_github_skills()

    # Phase 4B — Skill Gap Analysis
    print("\n🎯 Running Skill Gap Agent...\n")
    all_analyses     = high + medium
    skill_gap_report = run_skill_gap_analysis(all_analyses, github_skills)

    # Phase 5A — Store to Notion
    notion_updated = True
    try:
        store_to_notion(all_analyses, skill_gap_report)
    except Exception as e:
        notion_updated = False
        print(f"\n  ❌ Notion update failed: {e}\n")

    # Phase 5B — Update Google Doc
    doc_updated = update_google_doc(all_analyses, skill_gap_report, high, medium, GOOGLE_DOC_ID)

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
    print_skill_gap_summary(skill_gap_report)
    print(f"\n📔 Notion:     {'updated' if notion_updated else 'failed'}")
    print(f"📄 Google Doc: {'updated' if doc_updated else 'failed'}")
