"""
GitHub Skill Intelligence Agent

Scans your GitHub profile to understand your current skill set.

Extracts:
- Programming languages (from all repos)
- Frameworks and libraries (from repo topics + README patterns)
- Repository topics you've tagged
- Your most active areas

This builds your CURRENT skill profile which the Skill Gap Agent
will compare against newsletter trends.
"""

import requests
from config import GITHUB_TOKEN

GITHUB_USERNAME = "sri-sruthi"   # your GitHub username
HEADERS         = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
BASE_URL = "https://api.github.com"


def get_all_repos() -> list:
    """
    Fetches all public repositories for the user.
    Handles pagination — GitHub returns max 100 per page.
    """
    repos = []
    page  = 1

    while True:
        response = requests.get(
            f"{BASE_URL}/users/{GITHUB_USERNAME}/repos",
            headers=HEADERS,
            params={"per_page": 100, "page": page, "sort": "updated"}
        )

        if response.status_code != 200:
            print(f"  ⚠️  GitHub API error: {response.status_code}")
            break

        batch = response.json()
        if not batch:
            break

        repos.extend(batch)
        page += 1

    return repos


def get_repo_languages(repo_full_name: str) -> dict:
    """
    Gets language breakdown for a single repo.
    Returns dict like {"Python": 12500, "JavaScript": 3200}
    Values are bytes of code.
    """
    response = requests.get(
        f"{BASE_URL}/repos/{repo_full_name}/languages",
        headers=HEADERS
    )
    if response.status_code == 200:
        return response.json()
    return {}


def get_repo_topics(repo_full_name: str) -> list:
    """
    Gets topics tagged on a repo.
    e.g. ["machine-learning", "python", "deep-learning"]
    """
    response = requests.get(
        f"{BASE_URL}/repos/{repo_full_name}/topics",
        headers={**HEADERS, "Accept": "application/vnd.github.mercy-preview+json"}
    )
    if response.status_code == 200:
        return response.json().get("names", [])
    return []


def build_skill_profile(repos: list) -> dict:
    """
    Aggregates skills across all repos into a profile.

    Returns:
    {
        "languages": {"Python": 85000, "JavaScript": 12000},
        "topics":    ["machine-learning", "deep-learning", "web-scraping"],
        "repo_count": 12,
        "active_repos": ["repo1", "repo2"]  — updated in last 6 months
    }
    """
    all_languages = {}
    all_topics    = set()
    active_repos  = []

    print(f"  📊 Scanning {len(repos)} repositories...\n")

    for repo in repos:
        name      = repo['full_name']
        is_fork   = repo.get('fork', False)
        is_empty  = repo.get('size', 0) == 0

        # Skip forks and empty repos — they don't reflect your skills
        if is_fork or is_empty:
            continue

        # Get languages
        languages = get_repo_languages(name)
        for lang, bytes_count in languages.items():
            all_languages[lang] = all_languages.get(lang, 0) + bytes_count

        # Get topics from repo metadata (faster than API call)
        topics = repo.get('topics', [])
        all_topics.update(topics)

        # Track active repos (non-fork, non-empty)
        active_repos.append(repo['name'])

    return {
        "languages":   all_languages,
        "topics":      list(all_topics),
        "repo_count":  len(repos),
        "active_repos": active_repos[:10]  # top 10 most recently updated
    }


def extract_github_skills() -> dict:
    """
    Main function — fetches repos and builds skill profile.

    Returns clean skill summary:
    {
        "languages": ["Python", "JavaScript", ...],    # sorted by usage
        "topics":    ["machine-learning", ...],
        "raw_languages": {"Python": 85000, ...}        # for weighting
    }
    """
    print(f"🐙 Fetching GitHub profile for '{GITHUB_USERNAME}'...\n")

    repos = get_all_repos()
    if not repos:
        print("  ⚠️  No repositories found.")
        return {"languages": [], "topics": [], "raw_languages": {}}

    profile = build_skill_profile(repos)

    # Sort languages by bytes of code (most used first)
    sorted_langs = sorted(
        profile["languages"].items(),
        key=lambda x: x[1],
        reverse=True
    )

    skill_summary = {
        "languages":     [lang for lang, _ in sorted_langs],
        "topics":        profile["topics"],
        "raw_languages": profile["languages"],
        "active_repos":  profile["active_repos"],
        "repo_count":    profile["repo_count"]
    }

    # Print summary
    print(f"  ✅ Scanned {profile['repo_count']} repos")
    print(f"  💻 Languages: {skill_summary['languages'][:8]}")
    print(f"  🏷️  Topics:    {skill_summary['topics'][:10]}\n")

    return skill_summary
