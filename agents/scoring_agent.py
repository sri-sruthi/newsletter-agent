"""
Value Scoring Agent

Scores each newsletter on 3 criteria:
    1. Relevance  — how relevant is this to tech/developer growth?
    2. Novelty    — does it introduce new tools or emerging topics?
    3. Depth      — is it a surface headline or a deep technical piece?

Total score = sum of three (max 10 each = 30 total, normalised to 10)

Decision thresholds:
    Score >= 7  → HIGH VALUE  → label in Gmail
    Score 5–6.9 → MEDIUM      → leave in inbox
    Score < 5   → LOW VALUE   → archive in Gmail
"""

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

def score_newsletter(analysis: dict) -> dict:
    """
    Sends the content analysis to Groq for scoring.
    Returns the analysis dict with score fields added.
    """

    prompt = f"""
You are scoring a tech newsletter for a software developer's personal knowledge system.

Score this newsletter on three criteria, each from 1 to 10:

1. RELEVANCE (1-10)
   - 9-10: Directly about AI, ML, software engineering, developer tools
   - 6-8:  Tech-adjacent, useful industry context
   - 3-5:  Loosely related to tech
   - 1-2:  Barely relevant

2. NOVELTY (1-10)
   - 9-10: Introduces brand new tools, models, or techniques just released
   - 6-8:  Covers recent developments from the past few weeks
   - 3-5:  Known topics but with fresh angles
   - 1-2:  Well-known information, nothing new

3. DEPTH (1-10)
   - 9-10: Technical deep-dive, tutorials, research papers, code examples
   - 6-8:  Explains concepts with some technical substance
   - 3-5:  Overview level, touches on ideas without depth
   - 1-2:  Pure headline/news with no educational content

Then compute:
- final_score: average of the three scores, rounded to 1 decimal
- decision: "HIGH" if final_score >= 7, "MEDIUM" if 5-6.9, "LOW" if < 5

Respond ONLY with this JSON (no markdown, no extra text):
{{
  "relevance": <1-10>,
  "novelty": <1-10>,
  "depth": <1-10>,
  "final_score": <1.0-10.0>,
  "decision": "HIGH" or "MEDIUM" or "LOW",
  "reason": "one sentence explaining the score"
}}

Newsletter to score:
Subject:  {analysis['subject']}
Topics:   {analysis.get('topics', [])}
Tools:    {analysis.get('tools', [])}
Skills:   {analysis.get('skills', [])}
Summary:  {analysis.get('summary', '')}
"""

    for idx, model in enumerate(MODEL_GROQ_SMALL_CANDIDATES, start=1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )

            raw = _clean_json_response(response.choices[0].message.content.strip())
            scores = json.loads(raw)

            # Recompute score and decision locally to avoid float/model threshold drift.
            r = int(scores.get("relevance", 5))
            n = int(scores.get("novelty", 5))
            d = int(scores.get("depth", 5))
            final = round((r + n + d) / 3, 1)

            if final >= 7.0:
                decision = "HIGH"
            elif final >= 5.0:
                decision = "MEDIUM"
            else:
                decision = "LOW"

            analysis["relevance"] = r
            analysis["novelty"] = n
            analysis["depth"] = d
            analysis["final_score"] = final
            analysis["decision"] = decision
            analysis["score_reason"] = scores.get("reason", "")
            return analysis

        except Exception as e:
            is_last = idx == len(MODEL_GROQ_SMALL_CANDIDATES)
            if (_is_model_error(e) or _is_retryable_groq_error(e)) and not is_last:
                print(f"  ⚠️  Scoring model '{model}' unavailable/rate-limited, trying fallback...")
                continue

            print(f"  ⚠️  Scoring error for '{analysis['subject'][:40]}': {e}")
            analysis.update({
                "relevance": 5,
                "novelty": 5,
                "depth": 5,
                "final_score": 5.0,
                "decision": "MEDIUM",
                "score_reason": "Scoring failed — defaulted to MEDIUM",
            })
            return analysis

    analysis.update({
        "relevance": 5,
        "novelty": 5,
        "depth": 5,
        "final_score": 5.0,
        "decision": "MEDIUM",
        "score_reason": "Scoring fallback — defaulted to MEDIUM",
    })
    return analysis


def score_all_newsletters(analyses: list) -> tuple:
    """
    Scores all newsletters and splits them into three buckets.

    Returns:
        high   — score >= 7, label in Gmail
        medium — score 5-6.9, leave as is
        low    — score < 5, archive
    """
    high   = []
    medium = []
    low    = []

    print(f"⭐ Scoring {len(analyses)} newsletters...\n")

    for analysis in analyses:
        scored = score_newsletter(analysis)
        score  = scored['final_score']
        dec    = scored['decision']

        icon = "🔴" if dec == "LOW" else "🟡" if dec == "MEDIUM" else "🟢"

        print(f"  {icon} {dec:<6} | Score {score}/10 | {scored['subject'][:50]}")
        print(f"         | R:{scored['relevance']} N:{scored['novelty']} D:{scored['depth']} | {scored['score_reason']}\n")

        if dec == "HIGH":
            high.append(scored)
        elif dec == "MEDIUM":
            medium.append(scored)
        else:
            low.append(scored)

    print(f"📊 Scoring result: 🟢 {len(high)} high / 🟡 {len(medium)} medium / 🔴 {len(low)} low\n")
    return high, medium, low
