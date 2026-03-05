"""
Filter Agent — Smart two-stage filtering.

Stage 1: Structural junk removal (system alerts, promos) — no API cost
Stage 2: Groq intent filter — topic-agnostic, purpose-driven

Key fix: uses whole-word regex matching to avoid substring false positives
e.g. "ai" should NOT match "faith", "paid", "trail", "rain"
"""

import re
import json
from groq import Groq
from config import GROQ_API_KEY, MODEL_GROQ_SMALL_CANDIDATES

client = Groq(api_key=GROQ_API_KEY)


def _clean_json_response(raw: str) -> str:
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _is_retryable_groq_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "rate limit" in msg
        or "429" in msg
        or "temporarily unavailable" in msg
    )


def _is_model_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "decommissioned" in msg
        or "model_not_found" in msg
        or "invalid_request_error" in msg
        or "unknown model" in msg
    )

# ── Stage 1A: Structural junk — always discard ──────────────────────────────
# These identify emails by STRUCTURE, not topic.
# Plain substring match is fine here — these phrases are specific enough.

STRUCTURAL_JUNK = [
    "storage is full",
    "out of storage",
    "out of gmail storage",
    "verify your email",
    "password reset",
    "security alert",
    "sign-in attempt",
    "payment failed",
    "subscription renewed",
    "your invoice",
    "% off",
    "promo code",
    "coupon",
    "sale ends",
    "limited time offer",
    # Adding these — clearly non-tech structural patterns
    "unsubscribe from",
    "manage your preferences",
    "you are receiving this",
    "view in browser",
]


# ── Stage 1B: Obvious tech signals — always keep, skip Groq ─────────────────
# These are WHOLE WORDS only (regex word boundaries).
# Specific enough that a match = definitely relevant.
# Keeps Groq API calls low for clearly tech emails.

# ── Stage 1B: Obvious tech signals — whole-word regex ───────────────────────
# Rules for being on this list:
#   1. Must be 4+ characters
#   2. Must be unambiguous — can ONLY appear in a tech context
#   3. When in doubt, remove it and let Groq handle it
#
# Removed (too risky): \bai\b, \bapi\b, \brag\b, \bjax\b, \bgpt\b (matches "Egypt")
# \bgpt\b is actually safe since "gpt" never appears in non-tech contexts — kept
# \bapi\b removed — appears in "capitalism", "rapid", "happiness"

CLEAR_TECH_SIGNALS = [
    # AI models / companies — unambiguous
    r"\bgpt-\d",            # GPT-4, GPT-5 etc — the dash makes it unambiguous
    r"\bllm\b",             # too niche to appear outside tech
    r"\bopenai\b",
    r"\banthropic\b",
    r"\bgroq\b",
    r"\bmistral\b",
    r"\bgemini\b",          # safe — only means Google's AI in modern context
    r"\bllama\b",           # Meta's model — niche enough
    r"\blangchain\b",
    r"\blanggraph\b",
    r"\bhugging face\b",

    # Dev tools — unambiguous
    r"\bgithub\b",
    r"\bdocker\b",
    r"\bkubernetes\b",
    r"\bdevops\b",
    r"\bci/cd\b",
    r"\bpull request\b",

    # Languages / frameworks — unambiguous in context
    r"\bpython\b",
    r"\bjavascript\b",
    r"\btypescript\b",
    r"\breact\.js\b",
    r"\bnext\.js\b",
    r"\bnode\.js\b",
    r"\brust\b",            # safe — almost always programming in tech emails

    # Concepts — long enough to be unambiguous
    r"\bmachine learning\b",
    r"\bdeep learning\b",
    r"\bneural network\b",
    r"\bvector database\b",
    r"\blarge language model\b",
    r"\bopen source\b",
    r"\breinforcement learning\b",
    r"\bnatural language processing\b",
    r"\bsdlc\b",
    r"\bfullstack\b",
    r"\bfrontend\b",
    r"\bbackend\b",
    r"\bcloudflare\b",
]


def whole_word_match(patterns: list, text: str) -> str | None:
    """
    Returns the first pattern that matches as a whole word.
    Uses regex \b boundaries to prevent substring matches.
    e.g. \bai\b will NOT match 'faith', 'paid', 'trail'
    """
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return pattern
    return None


def stage1_filter(email: dict) -> tuple:
    """
    Fast structural check — no API cost.

    Returns:
        ("keep", reason)    — clear tech signal found
        ("discard", reason) — structural junk found
        ("check", reason)   — unclear, needs Groq
    """
    text = (email['subject'] + " " + email['body'][:500]).lower()

    # Check structural junk first (plain substring — phrases are specific)
    for junk in STRUCTURAL_JUNK:
        if junk in text:
            return "discard", f"structural junk: '{junk}'"

    # Check clear tech signals (whole-word regex)
    matched = whole_word_match(CLEAR_TECH_SIGNALS, text)
    if matched:
        return "keep", f"clear tech signal: '{matched}'"

    # Unclear — let Groq decide
    return "check", "no clear signal — sending to Groq"


def stage2_groq_filter(email: dict) -> tuple:
    """
    Groq decides based on PURPOSE of the system.
    Topic-agnostic — can discover entirely new fields.
    Strict: must have genuine skill-building value.

    Returns (should_keep: bool, reason: str, potential_skills: list)
    """

    prompt = f"""
You are a strict filter for a "Personal Knowledge & Skill Orchestrator" — 
an AI system that helps software developers discover new skills and technologies.

Your job: decide if this email has GENUINE value for a developer's professional growth.

KEEP if the email:
- Teaches or introduces a specific technology, tool, framework, or programming concept
- Covers AI/ML/data science developments with technical depth
- Discusses software engineering practices, architecture, or developer productivity
- Covers emerging tech fields that developers should know about
- Contains a course, tutorial, or technical deep-dive

DISCARD if the email:
- Is a system notification (storage, account, billing, security)
- Is a generic news update with no tech learning value
- Is about lifestyle, health, wellness, psychology, religion, or personal development
- Is about finance, stocks, economy with no direct tech relevance
- Is about marketing, business, or entrepreneurship with no technical content
- Is vague tech-adjacent but teaches nothing concrete (e.g. "startups are growing!")
- Mentions AI/tech only in passing but is fundamentally about something else

Be STRICT. If an email only mentions tech in passing, discard it.
Only keep emails where a developer would genuinely learn something technical.

Respond ONLY with this JSON (no markdown, no extra text):
{{"keep": true or false, "reason": "one sentence", "potential_skills": ["skill1", "skill2"]}}

potential_skills: what a developer could learn from this. Empty [] if discarding.

Email Subject: {email['subject']}
Email Sender: {email['sender']}
Email Body (first 600 chars):
{email['body'][:600]}
"""

    for idx, model in enumerate(MODEL_GROQ_SMALL_CANDIDATES, start=1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150
            )

            raw = _clean_json_response(response.choices[0].message.content.strip())
            result = json.loads(raw)

            keep = result.get("keep", False)
            reason = result.get("reason", "Groq decision")
            potential_skills = result.get("potential_skills", [])
            return keep, reason, potential_skills

        except Exception as e:
            is_last = idx == len(MODEL_GROQ_SMALL_CANDIDATES)
            tag = f"[{model}]"

            if _is_model_error(e) and not is_last:
                print(f"    ⚠️  Groq filter model unavailable {tag}, trying next model...")
                continue

            if _is_retryable_groq_error(e) and not is_last:
                print(f"    ⚠️  Groq filter rate-limited {tag}, trying next model...")
                continue

            print(f"    ⚠️  Groq filter error {tag}, keeping by default: {e}")
            return True, "filter error — kept by default", []

    return True, "filter fallback — kept by default", []


def filter_newsletters(emails: list) -> tuple:
    """
    Main filter pipeline.
    Returns:
        kept      — list of relevant emails to analyze
        discarded — list of irrelevant emails to archive in Gmail
    """
    kept      = []
    discarded = []

    print(f"🔎 Filtering {len(emails)} emails...\n")

    for email in emails:
        preview = email['subject'][:55]

        decision, reason = stage1_filter(email)

        if decision == "discard":
            print(f"  🗑️  DISCARD  | {preview}")
            print(f"             | {reason}\n")
            discarded.append(email)

        elif decision == "keep":
            print(f"  ✅ KEEP     | {preview}")
            print(f"             | {reason}\n")
            kept.append(email)

        else:
            # Unclear — ask Groq
            print(f"  🤔 CHECKING | {preview}")
            print(f"             | {reason}")
            keep, groq_reason, skills = stage2_groq_filter(email)

            if keep:
                email['potential_skills'] = skills
                print(f"  ✅ KEEP     | Groq: {groq_reason}")
                if skills:
                    print(f"             | Potential skills: {skills}")
                kept.append(email)
            else:
                print(f"  🗑️  DISCARD  | Groq: {groq_reason}")
                discarded.append(email)  # ← now tracked
            print()

    print(f"\n📊 Filter result: {len(kept)} kept / {len(discarded)} discarded / {len(emails)} total\n")
    return kept, discarded  # ← now returns both
