import json
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

# We're using Llama 3.3 70B — powerful, free on Groq's free tier
MODEL = "llama-3.3-70b-versatile"


def analyze_newsletter(email: dict) -> dict:
    """
    Sends one email to Groq (Llama 3.3 70B) and extracts:
    - summary
    - topics
    - tools mentioned
    - skills mentioned

    Returns a structured dict.
    """

    prompt = f"""
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

Email Subject: {email['subject']}
Email Sender: {email['sender']}
Email Body:
{email['body']}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,     # low = consistent structured output
            max_tokens=500
        )

        raw = response.choices[0].message.content.strip()

        # Sometimes models wrap in ```json ... ``` even when told not to
        # This cleans it just in case
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        analysis = json.loads(raw)

        # Attach original email metadata
        analysis['email_id'] = email['id']
        analysis['subject']  = email['subject']
        analysis['sender']   = email['sender']
        analysis['date']     = email['date']

        return analysis

    except json.JSONDecodeError:
        print(f"⚠️  JSON parse failed for: {email['subject']}")
        return {
            'email_id': email['id'],
            'subject':  email['subject'],
            'sender':   email['sender'],
            'date':     email['date'],
            'summary':  'Could not analyze.',
            'topics':   [],
            'tools':    [],
            'skills':   []
        }

    except Exception as e:
        print(f"❌ Groq error for '{email['subject']}': {e}")
        return None


def analyze_all_newsletters(emails: list) -> list:
    """
    Runs analyze_newsletter() on every email.
    Returns a list of analysis dicts.
    """
    results = []

    for i, email in enumerate(emails):
        print(f"🔍 Analyzing {i+1}/{len(emails)}: {email['subject'][:60]}...")
        analysis = analyze_newsletter(email)
        if analysis:
            results.append(analysis)

    print(f"\n✅ Analyzed {len(results)} newsletters.")
    return results