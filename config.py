import os
from dotenv import load_dotenv

load_dotenv()


def _csv_models(env_key: str, default: str) -> list[str]:
    raw = os.getenv(env_key, default)
    return [m.strip() for m in raw.split(",") if m.strip()]


# ── API Keys ──────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Model routing ─────────────────────────────────────────────────
# Groq small — for filter + scoring (simple classification)
MODEL_GROQ_SMALL = os.getenv("MODEL_GROQ_SMALL", "llama-3.1-8b-instant")

# Groq large — deeper fallback when content model is rate-limited
MODEL_GROQ_LARGE = os.getenv("MODEL_GROQ_LARGE", "llama-3.3-70b-versatile")

# Groq content — primary model for newsletter understanding
MODEL_GROQ_CONTENT = os.getenv("MODEL_GROQ_CONTENT", "llama-3.1-8b-instant")

# Candidate model lists for graceful fallback if a model is deprecated/rate-limited
MODEL_GROQ_SMALL_CANDIDATES = _csv_models(
    "MODEL_GROQ_SMALL_CANDIDATES",
    f"{MODEL_GROQ_SMALL},{MODEL_GROQ_LARGE}"
)
MODEL_GROQ_LARGE_CANDIDATES = _csv_models(
    "MODEL_GROQ_LARGE_CANDIDATES",
    f"{MODEL_GROQ_LARGE},{MODEL_GROQ_SMALL}"
)
MODEL_GROQ_CONTENT_CANDIDATES = _csv_models(
    "MODEL_GROQ_CONTENT_CANDIDATES",
    f"{MODEL_GROQ_CONTENT},openai/gpt-oss-20b,{MODEL_GROQ_LARGE}"
)

# Cost/rate-limit controls
EMAIL_BODY_CHAR_LIMIT = int(os.getenv("EMAIL_BODY_CHAR_LIMIT", "2400"))
CONTENT_AGENT_DELAY_SECONDS = float(os.getenv("CONTENT_AGENT_DELAY_SECONDS", "2"))

# ── Coming in later phases ────────────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN")
NOTION_TOKEN  = os.getenv("NOTION_TOKEN")
NOTION_DB_ID  = os.getenv("NOTION_DB_ID")
GOOGLE_DOC_ID = os.getenv("GOOGLE_DOC_ID")
