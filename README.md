# Universal Basic Lobbyist

AI-powered civic engagement assistant for San Francisco residents. Monitors local news and government activity, generates personalized weekly digests with high-leverage action recommendations.

## Setup

### 1. Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier works)
- An [Anthropic](https://console.anthropic.com) API key
- A [Resend](https://resend.com) account for email delivery

### 2. Install

```bash
git clone <repo-url> && cd ubl
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Then fill in your API keys
```

### 3. Database

Run `schema.sql` in your Supabase project's SQL Editor (Dashboard → SQL Editor → paste and run).

Then seed your user profile:

```bash
python seed_user.py
# Copy the FOUNDER_USER_ID from the output into your .env
```

### 4. Political Context

Copy the example template and fill in current SF political data:

```bash
cp ubl/prompts/sf_political_context.example.md ubl/prompts/sf_political_context.md
```

Edit `sf_political_context.md` with current Board of Supervisors info, political dynamics, and upcoming votes. This file is gitignored — it contains editorial judgments that are managed manually.

## Running Locally

```bash
# Full pipeline dry run (fetches articles, generates digest, saves email locally)
python -m ubl.jobs.cron --dry-run

# Just the ingestion pipeline
python -m ubl.pipeline.run

# Just the digest generation
python -m ubl.digest.run

# Real run (sends email)
python -m ubl.jobs.cron --send

# Run tests
python -m pytest tests/ -v
```

Dry-run output is saved to `output/digest_YYYY-MM-DD.html` — open in a browser to inspect.

## Project Structure

```
ubl/
  ubl/
    config.py         # Settings, env vars, feed registry
    models.py         # Pydantic models (data contracts between modules)
    pipeline/         # Data ingestion
      ingest.py       # RSS fetching
      classify.py     # Haiku 4.5 article classification
      store.py        # Supabase read/write
      run.py          # Ingestion orchestrator
    digest/           # Digest generation
      generate.py     # Sonnet 4.5 digest writing
      leverage.py     # Sonnet 4.5 + extended thinking leverage assessment
      draft.py        # Action drafting
      run.py          # Digest orchestrator
    delivery/         # Email delivery
      email.py        # Resend sending + Jinja2 rendering
      templates/      # Email HTML templates
    prompts/          # All LLM prompts (edit these to tune output)
    jobs/
      cron.py         # Entry point for scheduled runs
```

## Prompts

All prompts live in `ubl/prompts/` as separate markdown files. Each file has a header comment explaining which model uses it, what inputs it expects, and what output it produces. Edit prompts to tune classification, digest quality, and leverage assessment without touching Python code.

## Deployment

The pipeline runs via GitHub Actions on a weekly cron schedule (Sunday 2 PM UTC). Add your secrets in the repo's Settings → Secrets:

- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `RESEND_API_KEY`
- `FOUNDER_EMAIL`
- `FOUNDER_USER_ID`
