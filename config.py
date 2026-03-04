import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Coming in later phases ──────────────────────────────────────
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN")    # Phase 4
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")    # Phase 5
NOTION_DB_ID   = os.getenv("NOTION_DB_ID")    # Phase 5
GOOGLE_DOC_ID  = os.getenv("GOOGLE_DOC_ID")   # Phase 5