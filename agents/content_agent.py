"""
Content Intelligence Agent

Groq-only provider with model fallback.
"""

import json
import time
from groq import Groq
from config import (
    GROQ_API_KEY,
    MODEL_GROQ_CONTENT_CANDIDATES,
    EMAIL_BODY_CHAR_LIMIT,
    CONTENT_AGENT_DELAY_SECONDS,
)

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def _clean_json_response(raw: str) -> str:
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _attach_email_metadata(analysis: dict, email: dict) -> dict:
    analysis["email_id"] = email["id"]
    analysis["subject"] = email["subject"]
    analysis["sender"] = email["sender"]
    analysis["date"] = email["date"]
    return analysis


def _analysis_fallback(email: dict, reason: str) -> dict:
    return {
        "email_id": email["id"],
        "subject": email["subject"],
        "sender": email["sender"],
        "date": email["date"],
        "summary": f"Could not analyze automatically ({reason}).",
        "topics": [],
        "tools": [],
        "skills": [],
    }


def _is_rate_or_quota_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "resource_exhausted" in msg
        or "quota exceeded" in msg
        or "rate limit" in msg
        or "429" in msg
    )


def _is_model_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "model_not_found" in msg
        or "decommissioned" in msg
        or "unknown model" in msg
        or "invalid model" in msg
    )


def _build_prompt(email: dict) -> str:
    body = email["body"][:EMAIL_BODY_CHAR_LIMIT]
    return f"""
You are an AI assistant that analyzes tech newsletters.

Analyze the following email and return a JSON object with exactly these fields:
- "summary": a 2-3 sentence summary of what this email is about
- "topics": a list of main topics discussed (e.g. ["AI Agents", "Vector Databases"])
- "tools": a list of specific tools, libraries, or frameworks mentioned (e.g. ["LangChain", "ChromaDB"])
- "skills": a list of skills a developer would need to work with this content (e.g. ["Python", "Prompt Engineering"])

Rules:
- Return ONLY valid JSON. No explanation, no markdown, no extra text.
- Do NOT wrap in ```json blocks. Raw JSON only.
- If a field has nothing relevant, return an empty list [].
- Keep lists concise, max 5 items each.

Email Subject: {email["subject"]}
Email Sender: {email["sender"]}
Email Body (truncated):
{body}
"""


def _analyze_with_groq(prompt: str, model: str) -> dict:
    response = groq_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300
    )
    raw = _clean_json_response(response.choices[0].message.content.strip())
    return json.loads(raw)


def analyze_newsletter(email: dict) -> dict:
    """
    Analyze one newsletter with Groq model fallback.
    Always returns a dict so pipeline can continue.
    """
    prompt = _build_prompt(email)

    if groq_client:
        for i, model in enumerate(MODEL_GROQ_CONTENT_CANDIDATES, start=1):
            try:
                analysis = _analyze_with_groq(prompt, model)
                return _attach_email_metadata(analysis, email)
            except Exception as e:
                is_last = i == len(MODEL_GROQ_CONTENT_CANDIDATES)
                if (_is_model_error(e) or _is_rate_or_quota_error(e)) and not is_last:
                    print(f"    ⚠️  Groq model '{model}' failed, trying next Groq model...")
                    continue
                print(f"    ⚠️  Groq failed on '{model}': {e}")
                break

    return _analysis_fallback(email, "Groq quota/model errors")


def analyze_all_newsletters(emails: list) -> list:
    """
    Runs analyze_newsletter() on every email.
    """
    results = []

    for i, email in enumerate(emails):
        print(f"🔍 Analyzing {i+1}/{len(emails)}: {email['subject'][:60]}...")
        analysis = analyze_newsletter(email)
        if analysis:
            results.append(analysis)
        time.sleep(CONTENT_AGENT_DELAY_SECONDS)

    print(f"\n✅ Analyzed {len(results)} newsletters.")
    return results
