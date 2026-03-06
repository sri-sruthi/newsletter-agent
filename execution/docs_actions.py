"""
Google Docs Execution Layer

Appends a structured daily knowledge log entry to a Google Doc.
Each run adds a new dated section — builds a running history
of what you learned and what gaps were detected.
"""

from datetime import date
from googleapiclient.errors import HttpError
import json
from agents.email_agent import get_docs_service


def append_to_doc(doc_id: str, content: str):
    """
    Appends text to the end of a Google Doc.
    """
    service = get_docs_service()

    # Read title for logging
    doc = service.documents().get(documentId=doc_id).execute()

    # Prefer appending by end-of-segment (more robust across evolving Docs structures).
    requests_body = [{
        'insertText': {
            'endOfSegmentLocation': {'segmentId': ''},
            'text': content
        }
    }]

    try:
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests_body}
        ).execute()
    except HttpError:
        # Fallback to index-based insertion for older/newer API behavior differences.
        body_content = doc.get('body', {}).get('content', [])
        end_index = body_content[-1].get('endIndex', 1) - 1 if body_content else 1
        if end_index < 1:
            end_index = 1
        fallback_body = [{
            'insertText': {
                'location': {'index': end_index},
                'text': content
            }
        }]
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': fallback_body}
        ).execute()

    return doc.get("title", "Untitled")


def build_log_entry(analyses: list, skill_gap_report: dict,
                    high: list, medium: list) -> str:
    """
    Builds a focused project recommendation entry.
    Notion handles the full knowledge base — Docs is for projects only.
    """
    today   = date.today().strftime("%B %d, %Y")
    divider = "─" * 50

    gaps     = skill_gap_report.get('skill_gaps', [])
    projects = skill_gap_report.get('project_ideas', [])

    entry  = f"\n{divider}\n"
    entry += f"📅 {today}\n"
    entry += f"{divider}\n\n"

    entry += f"🚨 SKILL GAPS THIS WEEK\n"
    for gap in gaps:
        icon = "🔴" if gap.get('priority') == 'HIGH' else "🟡" if gap.get('priority') == 'MEDIUM' else "🟢"
        entry += f"  {icon} {gap['skill']} — {gap.get('why_important', '')}\n"

    entry += f"\n💡 SUGGESTED PROJECTS\n\n"
    for i, p in enumerate(projects, 1):
        entry += f"  {i}. {p['title']} (~{p.get('estimated_time', '?')})\n"
        entry += f"     {p.get('description', '')}\n"
        entry += f"     📚 Uses:   {', '.join(p.get('skills_used', []))}\n"
        entry += f"     🎯 Learns: {', '.join(p.get('skills_learned', []))}\n"
        entry += f"     🔧 Tools:  {', '.join(p.get('tools', []))}\n\n"

    entry += f"📝 {skill_gap_report.get('summary', '')}\n\n"

    return entry


def update_google_doc(analyses: list, skill_gap_report: dict,
                      high: list, medium: list, doc_id: str):
    """
    Main function — builds and appends the daily log entry.
    """
    print("📄 Updating Google Doc knowledge log...\n")

    if not doc_id:
        print("  ❌ Google Doc update failed: GOOGLE_DOC_ID is empty.\n")
        return False

    try:
        entry = build_log_entry(analyses, skill_gap_report, high, medium)
        title = append_to_doc(doc_id, entry)
        print(f"  ✅ Google Doc updated successfully: {title} ({doc_id})\n")
        return True
    except HttpError as e:
        status = getattr(e.resp, "status", "unknown")
        payload = ""
        if getattr(e, "content", None):
            try:
                payload = json.dumps(json.loads(e.content.decode("utf-8")), indent=2)
            except Exception:
                payload = e.content.decode("utf-8", errors="ignore")
        print(f"  ❌ Google Doc update failed (HTTP {status}): {e}\n")
        if payload:
            print("     API response:")
            print(payload)
            print()
        print(f"     Make sure:\n"
              f"     1. Google Docs API is enabled in Cloud Console\n"
              f"     2. OAuth token is valid (from token.json or GOOGLE_TOKEN_JSON)\n"
              f"     3. GOOGLE_DOC_ID in .env is correct and belongs to the same Google account used in OAuth\n")
        return False
    except Exception as e:
        print(f"  ❌ Google Doc update failed: {e}\n")
        print(f"     Make sure:\n"
              f"     1. Google Docs API is enabled in Cloud Console\n"
              f"     2. OAuth token is valid (from token.json or GOOGLE_TOKEN_JSON)\n"
              f"     3. GOOGLE_DOC_ID in .env is correct and belongs to the same Google account used in OAuth\n")
        return False
