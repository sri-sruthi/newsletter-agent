from agents.email_agent import fetch_newsletters
from agents.filter_agent import filter_newsletters
from agents.content_agent import analyze_all_newsletters
from agents.redundancy_agent import detect_redundancy
from agents.scoring_agent import score_all_newsletters
from agents.github_agent import extract_github_skills
from agents.skill_gap_agent import run_skill_gap_analysis
from execution.gmail_actions import execute_gmail_actions


def print_skill_gap_summary(skill_gap_report: dict):
    """Prints skill gaps and project ideas in the final summary section."""
    skill_gaps = skill_gap_report.get("skill_gaps", [])
    project_ideas = skill_gap_report.get("project_ideas", [])

    print(f"\n🎯 Skill gaps identified: {len(skill_gaps)}")
    if skill_gaps:
        for i, gap in enumerate(skill_gaps, 1):
            priority = gap.get("priority", "UNKNOWN")
            skill = gap.get("skill", "Unknown skill")
            why = gap.get("why_important", "").strip()
            print(f"  {i}. [{priority}] {skill}")
            if why:
                print(f"     - {why}")

    print(f"\n💡 Project ideas generated: {len(project_ideas)}")
    if project_ideas:
        for i, project in enumerate(project_ideas, 1):
            title = project.get("title", "Untitled project")
            eta = project.get("estimated_time", "unknown duration")
            uses = ", ".join(project.get("skills_used", []))
            learns = ", ".join(project.get("skills_learned", []))
            tools = ", ".join(project.get("tools", []))

            print(f"  {i}. {title} ({eta})")
            if uses:
                print(f"     Uses: {uses}")
            if learns:
                print(f"     Learns: {learns}")
            if tools:
                print(f"     Tools: {tools}")


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
    all_analyses = high + medium  # use all kept emails for trend analysis
    skill_gap_report = run_skill_gap_analysis(all_analyses, github_skills)

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
