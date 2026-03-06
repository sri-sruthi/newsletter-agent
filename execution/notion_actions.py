"""
Notion Execution Layer

Stores the skill gap report and newsletter insights
into a Notion database as structured entries.

Each run appends new knowledge — builds up over time
into a personal knowledge base you can search and filter.
"""

import requests
from datetime import date
from config import NOTION_TOKEN, NOTION_DB_ID

HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Content-Type":   "application/json",
    "Notion-Version": "2022-06-28"
}


def create_notion_page(properties: dict) -> bool:
    """
    Creates a single page (row) in the Notion database.
    Returns True if successful.
    """
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": properties
    }

    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=payload
    )

    return response.status_code == 200


def build_properties(topic: str, type_: str, priority: str,
                     source: str, notes: str) -> dict:
    """
    Builds the Notion page properties dict.
    Maps our data to Notion's property format.
    """
    today = date.today().isoformat()

    return {
        "Topic": {
            "title": [{"text": {"content": topic[:100]}}]
        },
        "Type": {
            "select": {"name": type_}
        },
        "Priority": {
            "select": {"name": priority}
        },
        "Source": {
            "rich_text": [{"text": {"content": source[:200]}}]
        },
        "Date": {
            "date": {"start": today}
        },
        "Notes": {
            "rich_text": [{"text": {"content": notes[:500]}}]
        }
    }


def store_skill_gaps(skill_gap_report: dict):
    """Stores each skill gap as a Notion entry."""
    gaps = skill_gap_report.get("skill_gaps", [])
    if not gaps:
        return

    print(f"  📝 Storing {len(gaps)} skill gaps in Notion...")
    for gap in gaps:
        props = build_properties(
            topic    = gap['skill'],
            type_    = "Skill Gap",
            priority = gap.get('priority', 'MEDIUM').capitalize(),
            source   = "Skill Gap Agent",
            notes    = gap.get('why_important', '')
        )
        success = create_notion_page(props)
        status  = "✅" if success else "❌"
        print(f"    {status} Skill Gap: {gap['skill']}")


def store_project_ideas(skill_gap_report: dict):
    """Stores each project idea as a Notion entry."""
    projects = skill_gap_report.get("project_ideas", [])
    if not projects:
        return

    print(f"  📝 Storing {len(projects)} project ideas in Notion...")
    for project in projects:
        notes = (
            f"{project.get('description', '')}\n"
            f"Uses: {project.get('skills_used', [])}\n"
            f"Learns: {project.get('skills_learned', [])}\n"
            f"Tools: {project.get('tools', [])}\n"
            f"Time: {project.get('estimated_time', '')}"
        )
        props = build_properties(
            topic    = project['title'],
            type_    = "Project Idea",
            priority = "Medium",
            source   = "Skill Gap Agent",
            notes    = notes
        )
        success = create_notion_page(props)
        status  = "✅" if success else "❌"
        print(f"    {status} Project: {project['title']}")


def store_trending_topics(analyses: list):
    """Stores high-value newsletter topics as Notion entries."""
    seen = set()

    print(f"  📝 Storing trending topics from {len(analyses)} newsletters...")
    for analysis in analyses:
        for topic in analysis.get('topics', [])[:3]:
            if topic in seen:
                continue
            seen.add(topic)

            props = build_properties(
                topic    = topic,
                type_    = "Topic",
                priority = "Medium",
                source   = analysis.get('sender', 'Newsletter'),
                notes    = analysis.get('summary', '')[:300]
            )
            success = create_notion_page(props)
            status  = "✅" if success else "❌"
            print(f"    {status} Topic: {topic}")


def store_to_notion(analyses: list, skill_gap_report: dict):
    """
    Main function — stores everything to Notion.
    """
    print("\n📔 Storing to Notion...\n")
    store_trending_topics(analyses)
    store_skill_gaps(skill_gap_report)
    store_project_ideas(skill_gap_report)
    print("\n  ✅ Notion update complete.\n")