"""
Redundancy Detection Agent

If multiple emails cover the same topic, keep only the most informative one.
Archive the rest.

Method:
- Compare topics extracted by the Content Agent
- Group emails by topic overlap
- Within each group, keep the one with the most tools/skills/depth
- Mark the rest as redundant

This runs AFTER content analysis so we have topics to compare.
"""

def jaccard_similarity(set1: set, set2: set) -> float:
    """
    Measures overlap between two sets.
    Returns 0.0 (no overlap) to 1.0 (identical).

    Formula: size of intersection / size of union

    Example:
        set1 = {"AI Agents", "LLM", "Python"}
        set2 = {"LLM", "Python", "RAG"}
        intersection = {"LLM", "Python"} → size 2
        union = {"AI Agents", "LLM", "Python", "RAG"} → size 4
        similarity = 2/4 = 0.5
    """
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union)


SIMILARITY_THRESHOLD = 0.4  # 40% topic overlap = considered redundant


def score_informativeness(analysis: dict) -> int:
    """
    Quick score to decide which email to keep within a redundant group.
    More tools + skills + longer summary = more informative.
    """
    return (
        len(analysis.get('tools', [])) * 3 +   # tools are most valuable
        len(analysis.get('skills', [])) * 2 +  # skills second
        len(analysis.get('topics', [])) * 1 +  # topics third
        min(len(analysis.get('summary', '')), 300) // 50  # summary length bonus
    )


def detect_redundancy(analyses: list) -> tuple:
    """
    Groups similar emails and keeps only the most informative per group.

    Returns:
        kept      — list of analyses to keep
        redundant — list of analyses to archive (with reason attached)
    """
    if len(analyses) <= 1:
        return analyses, []

    kept      = []
    redundant = []
    assigned  = set()  # track which indices have been grouped

    print(f"🔁 Checking {len(analyses)} emails for redundancy...\n")

    for i, email_a in enumerate(analyses):
        if i in assigned:
            continue

        group       = [i]  # start a group with this email
        topics_a    = set(t.lower() for t in email_a.get('topics', []))

        for j, email_b in enumerate(analyses):
            if j <= i or j in assigned:
                continue

            topics_b   = set(t.lower() for t in email_b.get('topics', []))
            similarity = jaccard_similarity(topics_a, topics_b)

            if similarity >= SIMILARITY_THRESHOLD:
                group.append(j)
                assigned.add(j)
                print(f"  🔗 Similar ({similarity:.0%} overlap): ")
                print(f"     '{email_a['subject'][:50]}'")
                print(f"     '{email_b['subject'][:50]}'")

        assigned.add(i)

        if len(group) == 1:
            # No duplicates found — keep it
            kept.append(email_a)
        else:
            # Multiple similar emails — keep most informative, archive rest
            group_emails = [analyses[idx] for idx in group]
            group_emails.sort(key=score_informativeness, reverse=True)

            best = group_emails[0]
            kept.append(best)
            print(f"  ✅ Keeping most informative: '{best['subject'][:50]}'")

            for duplicate in group_emails[1:]:
                duplicate['redundancy_reason'] = (
                    f"Similar to '{best['subject'][:40]}'"
                )
                redundant.append(duplicate)
                print(f"  🗑️  Redundant: '{duplicate['subject'][:50]}'")
            print()

    print(f"\n📊 Redundancy result: {len(kept)} unique / {len(redundant)} redundant\n")
    return kept, redundant