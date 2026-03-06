# Autonomous Newsletter Agent and Skills Orchestrator

> Runs daily on Railway. Zero manual inbox management.

An AI pipeline that processes your Gmail newsletters, keeps technical content, archives noise, learns your skills from GitHub, detects gaps, and generates project ideas. It also writes results to Notion and Google Docs.

## What it does

Each run:

1. Fetches up to 20 unread inbox emails from Gmail.
2. Skips already-processed emails by excluding `High-Value` and `Medium-Value` labels.
3. Filters newsletters with a two-stage filter:
   - Stage 1: structural junk + clear tech regex signals
   - Stage 2: Groq intent classification for ambiguous emails
4. Analyzes kept newsletters (summary, topics, tools, skills).
5. Detects redundancy using topic Jaccard similarity.
6. Scores each unique newsletter on relevance, novelty, and depth.
7. Executes Gmail actions:
   - `HIGH`: label `High-Value` (left unread)
   - `MEDIUM`: label `Medium-Value` (left unread)
   - `LOW`: archive + mark read
   - filtered / redundant: archive + mark read
8. Tracks discarded senders in `memory/history.json` and auto-unsubscribes at threshold.
9. Builds GitHub skill profile from repositories.
10. Detects skill gaps + generates 3 project ideas.
11. Stores results in Notion and appends a weekly-style project/gap log to Google Docs.

## Architecture

```text
Gmail -> Filter -> Content Analysis -> Redundancy -> Scoring -> Gmail Actions
                                                          |
                                                          v
GitHub Profile ----------------------------------> Skill Gap + Projects
                                                          |
                                                          v
                                                  Notion + Google Docs
```

## Project structure

```text
newsletter-agent/
├── agents/
│   ├── email_agent.py
│   ├── filter_agent.py
│   ├── content_agent.py
│   ├── redundancy_agent.py
│   ├── scoring_agent.py
│   ├── github_agent.py
│   └── skill_gap_agent.py
├── execution/
│   ├── gmail_actions.py
│   ├── unsubscribe_actions.py
│   ├── notion_actions.py
│   └── docs_actions.py
├── memory/
│   └── memory_manager.py
├── main.py
├── config.py
├── Procfile
├── railway.toml
└── requirements.txt
```

## Core behavior from code

### Gmail fetch query

From `agents/email_agent.py`, the fetch query is:

```text
is:unread -label:High-Value -label:Medium-Value
```

This prevents re-processing of already labeled unread emails.

### Filtering

- Structural junk checks run first (substring rules).
- Clear tech signals use regex patterns.
- Ambiguous emails go to Groq with strict keep/discard JSON output.

### Redundancy

- Jaccard similarity over lowercased topic sets.
- `SIMILARITY_THRESHOLD = 0.4`.
- Keeps most informative email in each similar group.

### Scoring

- LLM returns relevance/novelty/depth.
- Final score and decision are recomputed locally:
  - `HIGH` if `>= 7.0`
  - `MEDIUM` if `>= 5.0`
  - `LOW` otherwise

### Unsubscribe memory

`memory/history.json` tracks:

```json
{
  "sender_discard_counts": {},
  "unsubscribed_senders": [],
  "whitelisted_senders": []
}
```

- Threshold defaults to `3` (`DISCARD_THRESHOLD` env override supported).
- Already-unsubscribed senders are skipped first.
- Whitelisted senders are excluded from discard counting/unsubscribe flow.

Note: whitelist affects unsubscribe tracking, not the content filter itself.

## Model routing (current defaults)

From `config.py`:

- `MODEL_GROQ_SMALL`: `llama-3.1-8b-instant`
- `MODEL_GROQ_LARGE`: `llama-3.3-70b-versatile`
- `MODEL_GROQ_CONTENT`: `llama-3.1-8b-instant`

Candidate fallbacks:

- `MODEL_GROQ_SMALL_CANDIDATES`: small -> large
- `MODEL_GROQ_CONTENT_CANDIDATES`: content -> `openai/gpt-oss-20b` -> large

`skill_gap_agent.py` currently uses `MODEL_GROQ_LARGE` directly.

## Authentication and tokens

Google auth is centralized in `agents/email_agent.py`.

Token loading priority:

1. `GOOGLE_TOKEN_JSON` env var (recommended for Railway)
2. `token.json` local file

Scopes requested:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/documents`

On local first run, OAuth browser flow is used if no valid token exists.

## Environment variables

Required:

- `GROQ_API_KEY`
- `GITHUB_TOKEN`
- `NOTION_TOKEN`
- `NOTION_DB_ID`
- `GOOGLE_DOC_ID`

For Railway/headless Google auth:

- `GOOGLE_TOKEN_JSON` (JSON string from a valid OAuth token with both scopes)

Optional tuning:

- `MODEL_GROQ_SMALL`
- `MODEL_GROQ_LARGE`
- `MODEL_GROQ_CONTENT`
- `MODEL_GROQ_SMALL_CANDIDATES`
- `MODEL_GROQ_LARGE_CANDIDATES`
- `MODEL_GROQ_CONTENT_CANDIDATES`
- `EMAIL_BODY_CHAR_LIMIT` (default `2400`)
- `CONTENT_AGENT_DELAY_SECONDS` (default `2`)
- `DISCARD_THRESHOLD` (default `3`)

## Prerequisites

- Python 3.10+
- A Gmail account
- A GitHub account (public repos)
- A Notion account
- A Google Cloud project with Gmail API + Docs API enabled

## Local setup

### 1) Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2) Google Cloud

1. Create a Google Cloud project.
2. Enable Gmail API and Google Docs API.
3. Create OAuth Desktop App credentials.
4. Save downloaded file as `credentials.json`.
5. Run once locally:

```bash
python main.py
```

This creates `token.json` after OAuth consent.

### 3) Notion

1. Create Notion integration.
2. Create/share database with properties:
   - `Topic` (title)
   - `Type` (select)
   - `Priority` (select)
   - `Source` (rich_text)
   - `Date` (date)
   - `Notes` (rich_text)

### 4) .env

```env
GROQ_API_KEY=...
GITHUB_TOKEN=...
NOTION_TOKEN=...
NOTION_DB_ID=...
GOOGLE_DOC_ID=...
```

### 5) Run

```bash
python main.py
```

## Railway deployment

### Current runtime config

- `Procfile`: `worker: python main.py`
- `railway.toml`:
  - `startCommand = "python main.py"`
  - cron schedule: `"0 2 * * *"` (02:00 UTC = 07:30 IST)

### Deploy steps

```bash
npm install -g @railway/cli
railway login --browserless
railway init
railway add --service newsletter-agent
railway service
railway variables set GROQ_API_KEY=...
railway variables set GITHUB_TOKEN=...
railway variables set NOTION_TOKEN=...
railway variables set NOTION_DB_ID=...
railway variables set GOOGLE_DOC_ID=...
railway variables set GOOGLE_TOKEN_JSON='{"token":"...","refresh_token":"...","client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token","scopes":["https://www.googleapis.com/auth/gmail.modify","https://www.googleapis.com/auth/documents"]}'
railway up
```

## Security notes

- Never commit `.env`, `token.json`, `token_docs.json`, or `credentials.json`.
- Rotate any API/OAuth secrets if they were ever committed.
- `.gitignore` should include at least:
  - `.env`
  - `credentials.json`
  - `token.json`
  - `token_docs.json`
  - `memory/history.json`
  - `venv/`

## Requirements

From `requirements.txt`:

- `google-auth`
- `google-auth-oauthlib`
- `google-auth-httplib2`
- `google-api-python-client`
- `groq`
- `python-dotenv`
- `requests`
- `notion-client`
