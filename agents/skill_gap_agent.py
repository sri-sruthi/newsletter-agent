"""
Skill Gap & Project Generator Agent

Compares:
    Your GitHub skill profile  (what you know)
        vs
    Newsletter trending topics (what's emerging)

Detects gaps and generates concrete project ideas
to help you close those gaps.

This is the core intelligence of the whole system —
it connects your inbox to your professional growth.
"""

import json
from groq import Groq
from config import GROQ_API_KEY, MODEL_GROQ_LARGE

client = Groq(api_key=GROQ_API_KEY)


def extract_trending_skills(analyses: list) -> dict:
    """
    Aggregates all topics, tools, and skills from newsletter analyses
    into a trending skills picture.

    Returns:
    {
        "topics": {"AI Agents": 3, "Vector DB": 2, ...},
        "tools":  {"LangChain": 2, "JAX": 1, ...},
        "skills": {"Python": 4, "Prompt Engineering": 2, ...}
    }
    """
    topics = {}
    tools  = {}
    skills = {}

    for analysis in analyses:
        for topic in analysis.get('topics', []):
            topics[topic] = topics.get(topic, 0) + 1
        for tool in analysis.get('tools', []):
            tools[tool] = tools.get(tool, 0) + 1
        for skill in analysis.get('skills', []):
            skills[skill] = skills.get(skill, 0) + 1

    # Sort by frequency
    return {
        "topics": dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)),
        "tools":  dict(sorted(tools.items(),  key=lambda x: x[1], reverse=True)),
        "skills": dict(sorted(skills.items(), key=lambda x: x[1], reverse=True))
    }


def detect_skill_gaps_and_generate_projects(
    github_skills: dict,
    trending: dict
) -> dict:
    """
    Sends both skill profiles to Groq and asks it to:
    1. Identify skill gaps (trending but not in your profile)
    2. Generate 3 concrete project ideas to close the gaps

    Returns structured gap analysis + project ideas.
    """

    prompt = f"""
You are a career development AI for a software developer.

You have two inputs:

1. DEVELOPER'S CURRENT SKILLS (from GitHub):
Languages: {github_skills.get('languages', [])[:10]}
Topics they work with: {github_skills.get('topics', [])}
Active repositories: {github_skills.get('active_repos', [])}

2. TRENDING TOPICS FROM THEIR NEWSLETTERS THIS WEEK:
Topics trending: {list(trending['topics'].keys())[:15]}
Tools mentioned: {list(trending['tools'].keys())[:15]}
Skills mentioned: {list(trending['skills'].keys())[:15]}

Your tasks:
A) SKILL GAP ANALYSIS
   - Compare the trending topics/tools/skills against the developer's current profile
   - Identify the most important gaps (things trending that they don't know yet)
   - Be specific — not just "learn AI" but "learn LangGraph for multi-agent orchestration"

B) PROJECT IDEAS
   - Generate exactly 3 concrete project ideas that would close the most important gaps
   - Each project should be buildable in 1-2 weeks
   - Each project should use at least one trending tool they don't currently know
   - Each project should build on skills they already have (bridge old → new)

Respond ONLY with this JSON (no markdown, no extra text):
{{
  "skill_gaps": [
    {{
      "skill": "name of missing skill",
      "why_important": "one sentence on why this matters now",
      "priority": "HIGH" or "MEDIUM" or "LOW"
    }}
  ],
  "project_ideas": [
    {{
      "title": "project name",
      "description": "2 sentence description",
      "skills_used": ["existing skill 1", "existing skill 2"],
      "skills_learned": ["new skill 1", "new skill 2"],
      "tools": ["tool1", "tool2"],
      "estimated_time": "X days"
    }}
  ],
  "summary": "2 sentence overall assessment of where the developer stands vs current trends"
}}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_GROQ_LARGE,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )

        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        return result

    except Exception as e:
        print(f"  ⚠️  Skill gap analysis failed: {e}")
        return {
            "skill_gaps":    [],
            "project_ideas": [],
            "summary":       "Analysis unavailable."
        }


def run_skill_gap_analysis(analyses: list, github_skills: dict) -> dict:
    """
    Main function — orchestrates the full skill gap analysis.
    """
    print("🔍 Extracting trending skills from newsletters...\n")
    trending = extract_trending_skills(analyses)

    print(f"  📈 Top trending topics: {list(trending['topics'].keys())[:5]}")
    print(f"  🔧 Top trending tools:  {list(trending['tools'].keys())[:5]}")
    print(f"  💡 Top trending skills: {list(trending['skills'].keys())[:5]}\n")

    print("🧠 Running skill gap analysis...\n")
    result = detect_skill_gaps_and_generate_projects(github_skills, trending)

    # Print results
    print("📊 SKILL GAP REPORT")
    print("="*60)

    print("\n🚨 Skill Gaps Detected:")
    for gap in result.get('skill_gaps', []):
        icon = "🔴" if gap['priority'] == "HIGH" else "🟡" if gap['priority'] == "MEDIUM" else "🟢"
        print(f"  {icon} {gap['skill']}")
        print(f"     {gap['why_important']}")

    print("\n💡 Suggested Projects:")
    for i, project in enumerate(result.get('project_ideas', []), 1):
        print(f"\n  {i}. {project['title']} (~{project['estimated_time']})")
        print(f"     {project['description']}")
        print(f"     Uses:   {project['skills_used']}")
        print(f"     Learns: {project['skills_learned']}")
        print(f"     Tools:  {project['tools']}")

    print(f"\n📝 Summary: {result.get('summary', '')}\n")

    return result