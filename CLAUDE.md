# UBL — Implementation Context for Claude Code

This document supplements the PRD with technical details, verified data sources, architecture decisions, and implementation guidance from the product design process. Read the PRD first, then use this for implementation specifics.

---

## 1. Verified Data Source URLs

These RSS feeds and APIs have been verified as working as of March 2026.

### RSS Feeds (confirmed working)

```
# Critical — full text, free
Mission Local:       https://missionlocal.org/feed
48 Hills:            https://48hills.org/feed
Streetsblog SF:      https://sf.streetsblog.org/feed

# High priority — free, section feeds available
SFGate (Bay Area):   https://sfgate.com/bayarea/feed/bay-area-news-702.php
SFGate (Politics):   https://sfgate.com/politics/feed  (confirm exact URL)
SFGate (Top News):   https://sfgate.com/rss/feed/Top-News...  (confirm exact URL)

# High priority — summaries only (paywalled full text, $9/mo)
SF Standard (all):   https://sfstandard.com/feed
SF Standard (news):  https://sfstandard.com/news/feed
SF Standard (politics): https://sfstandard.com/politics/feed
SF Standard (business): https://sfstandard.com/business/feed
# Note: SF Standard RSS returns valid XML. Per their RSS page, feeds deliver
# "headlines, summaries and links back to full articles." Summaries are
# sufficient for classification and relevance scoring. Full text requires
# subscription or scraping.

# Medium priority
KQED Politics:       https://kqed.org/politics  (has RSS, confirm exact feed URL)
SF Examiner:         https://sfexaminer.com  (has RSS, confirm exact feed URL)
SFist:               https://sfist.com/rss
GrowSF (Substack):   https://report.growsf.org/feed  (Substack built-in RSS)

# Lower priority / harder access
The Frisc:           No confirmed RSS. Newsletter-based. May need scraping from thefrisc.com
SFYIMBY:             https://sfyimby.org/blog  (infrequent, may need scraping)
TogetherSF Action:   Newsletter only, no RSS. Would need email parsing or scraping from tsfaction.org
SPUR:                https://spur.org  (blog + newsletter, confirm RSS)
```

### SF Chronicle — DO NOT USE
sfchronicle.com has a metered paywall and no discoverable public RSS feeds. Use SFGate instead — separate newsroom since 2019 but overlapping Hearst content, completely free with working RSS.

### Government APIs

```
# SF Board of Supervisors — Legistar
# Main interface: https://sfgov.legistar.com/
# Python Legistar Scraper exists and is documented:
# See: https://www.kvakil.me/posts/scraping_legistar.html
# Usage:
#   from legistar.bills import LegistarBillScraper
#   s = LegistarBillScraper()
#   s.BASE_URL = 'https://sfgov.legistar.com/'
#   s.LEGISLATION_URL = 'https://sfgov.legistar.com/Legislation.aspx'

# SF Open Data Portal (DataSF)
# Socrata API (SODA) — every dataset has an API
# Base: https://data.sfgov.org/
# Docs: https://data.sfgov.org/developers
# Auth: app token (free registration)
# Example: https://data.sfgov.org/resource/{dataset-id}.json

# California Legislature (for future state-level integration)
# https://leginfo.legislature.ca.gov/ — has API
# Also: Open States API (https://openstates.org/) provides normalized data
```

---

## 2. Architecture Decisions

### Project Structure

```
/ubl
  /pipeline              # Shared, built in Phase 0, reused in all phases
    ingest.py            # RSS fetching (feedparser + requests)
    legistar.py          # SF Board of Supervisors scraping
    classify.py          # Haiku 4.5 classification/tagging
    store.py             # Write to Supabase
  /digest                # Shared, built in Phase 0
    generate.py          # Takes user_profile + articles → digest
    leverage.py          # Sonnet reasoning about highest-leverage actions
    draft.py             # Action drafting (emails, public comments)
  /delivery              # Shared, built in Phase 0
    email.py             # Resend/SES sending
    templates/           # Email HTML templates
  /web                   # Added in Phase 1
    (Next.js app)        # Auth, onboarding, chat, billing, preferences
  /jobs
    cron.py              # Phase 0: runs once for founder
                         # Phase 1+: loops over all users
```

### Key Principle: Build for Multi-User from Day One

Even in Phase 0 (personal MVP), use Supabase as the database. Store:
- Classified articles in an `articles` table
- User profile as a row in a `users` table (just one row initially)
- Generated digests in a `digests` table

This way, Phase 1 is adding a web layer on top of a working multi-user-ready backend, not migrating from flat files.

The core function signature should be something like:
```python
def generate_digest(user_profile: dict, articles: list[dict], political_context: str) -> dict:
    """
    Takes a user profile, a set of classified/filtered articles, and the
    political context document. Returns a structured digest with summaries
    and action recommendations.
    """
```

Phase 0 calls this once with a hardcoded profile. Phase 1+ calls it in a loop over all users from the database.

---

## 3. Model Routing

Different LLM tasks require different models. This is a cost and quality optimization.

| Task | Model | Pricing (per MTok) | Why |
|------|-------|-------------------|-----|
| Article classification/tagging | Haiku 4.5 | $1 in / $5 out | High volume, low complexity. "Is this about housing?" |
| Relevance matching to user prefs | Haiku 4.5 | $1 in / $5 out | Score articles against user profile. Fast, cheap. |
| Digest writing (summaries) | Sonnet 4.5 via Batch API | $1.50 in / $7.50 out (50% batch discount) | Needs quality writing. Not real-time, so batch is fine. |
| Leverage assessment | Sonnet 4.5 + extended thinking | $3 in / $15 out (thinking tokens billed as output) | The "lobbyist brain." Needs to reason about timing, political dynamics, marginal impact. Budget 3-4K thinking tokens per assessment. |
| Action drafting (emails, comments) | Sonnet 4.5 | $3 in / $15 out | Needs to write specific, personalized, persuasive text. |
| Simple follow-up Q&A | Haiku 4.5 | $1 in / $5 out | "When is the next Board meeting?" Factual lookups. |
| Substantive follow-up | Sonnet 4.5 | $3 in / $15 out | "Tell me more about the rezoning proposal." |
| Strategic advice follow-up | Sonnet 4.5 + thinking | $3 in / $15 out | "Should I go to the hearing or write a letter?" |

### Cost Optimization Strategies

- **Batch API for digest generation:** Digests are generated in advance (e.g., Sunday night for Monday delivery), not real-time. Use the Batch API for 50% discount on the entire digest pipeline.
- **Prompt caching for shared content:** System prompt, political context document, and article summaries are largely shared across users. Cache these aggressively — 90% discount on cache reads.
- **Haiku for routing:** Before sending anything to Sonnet, use Haiku to classify and filter. Only relevant, scored articles go into the Sonnet digest generation call.

### Estimated Per-User Monthly API Cost

| Scenario | Cost |
|----------|------|
| Digest only (low engagement) | ~$0.82 |
| Digest + moderate follow-ups (~10/month) | ~$1.50 |
| Digest + heavy follow-ups (~20/month) | ~$3.00 |
| Blended average estimate | ~$1.50 |
| Blended with batch + caching optimizations | ~$0.90-1.20 |

---

## 4. System Prompt Guidance

### Political Context Document

The system prompt (or a knowledge base document referenced by it) needs to contain:

**Layer A (automated, refreshed weekly):** Board composition, committee assignments, voting records, legislative calendar, bill statuses. Pull from Legistar.

**Layer B (AI-generated, human-reviewed monthly):** Supervisor position summaries by issue area, policy trajectory analysis, advocacy landscape mapping.

**Layer C (human-curated):** Engagement effectiveness knowledge — what kinds of actions actually sway outcomes in SF. This is the most valuable and hardest-to-replicate content.

### Digest Generation Prompt — Key Instructions

The digest generation prompt should instruct the model to:
- Be concise — entire digest readable in 5 minutes
- Be specific — "Email Supervisor Chan about item 12 on Thursday's agenda" not "consider contacting your elected officials"
- Show its work — every recommendation explains the rationale and offers alternatives
- Be honest about uncertainty — "this might matter but we're not sure how close the vote will be"
- Never generate filler — if nothing high-leverage is happening, say "quiet week, here's some background reading"
- For politically charged actions (donations, campaigns): explicitly label the nature of the action and provide positions of all parties

### Leverage Assessment Prompt — Key Factors

When reasoning about what's "high leverage," the model should consider:
- **Timing:** Upcoming vote, hearing, or deadline? Window closing?
- **Marginal impact:** Is the outcome genuinely uncertain? Is this a close vote?
- **District relevance:** Is the user a constituent of a key decision-maker?
- **Specificity:** Is there a concrete ask? ("Vote yes on item 12" >> "please care about housing")
- **Channel match:** Is email, testimony, or public comment most effective for this issue?
- **User fit:** Does this match the user's engagement constraints (time, willingness to attend in-person, etc.)?

### State-Level Issues — Prompt Instructions

The MVP does not have automated state-level data ingestion, but the model should use its base knowledge to handle state-level issues intelligently. Include in the system prompt:

"When an issue is partly or fully controlled at the state level (e.g., rent regulation, school funding formulas, MTA governance, housing preemption bills), acknowledge this jurisdictional reality. Explain which level of government actually controls the outcome. Offer to draft communications to the user's state senator and assemblymember using your general knowledge. Be transparent that UBL does not actively monitor Sacramento legislation and that individual constituent leverage is lower with state legislators who represent 500K+ people vs. SF supervisors who represent ~80K. Frame state-level actions honestly: low expected individual impact, but low effort too — an email takes 1 minute and costs nothing."

This requires zero extra engineering — it's purely system prompt instructions. The model already knows which SF issues are state-controlled.

---

## 5. Onboarding — Preference Elicitation

### Layer 1: Fault Line Questions (60 seconds)

5-8 agree/disagree/skip statements. These should be plain language, not policy jargon.

Draft statements (to be refined):
1. "The city should make it easier to build apartment buildings" (housing density)
2. "The city's approach to homelessness should prioritize treatment and shelter over harm reduction" (street conditions)
3. "The city should prioritize public transit and bike lanes over car infrastructure" (transit)
4. "City government needs structural reform to be more accountable" (government reform)
5. "The city needs stricter enforcement of quality-of-life laws" (public safety)
6. "SFUSD needs significant reform, even if that means controversial changes like school closures" (education)

"Skip" = weak prior, not absence of signal.

### Layer 2: Optional Depth

After each Layer 1 response, optional "tell me more" — either follow-up questions or free text box. Most users skip.

### Layer 3: Reactive Preference Learning

Each digest item in the web console has: "more like this / less like this / I have thoughts"
- "More/less" is a lightweight signal that refines the relevance model
- "I have thoughts" opens a text input for richer signal
- Users can also reply conversationally to any digest content via the chat interface
- Preferences captured reactively (in response to real events) are richer than abstract survey responses

### Additional Intake
- Address or zip → auto-detect district, confirm
- Voter registration status (yes / no / not sure)
- Engagement preferences: time per week (5 min / 20 min / 1 hour+), willingness for in-person (yes / no / maybe), financial engagement comfort (yes / no / not for political campaigns)

---

## 6. Email Digest Format

### Structure

```
Subject: Your UBL Weekly — [Month Day]

1. WHAT HAPPENED THIS WEEK
   [3-5 items, ranked by relevance to user priorities]

   Each item:
   - Headline / summary (2-3 sentences)
   - Why this matters for you specifically (1-2 sentences, referencing user prefs/district)
   - Source link

2. RECOMMENDED ACTIONS
   [1-3 items, ranked by leverage]

   Each item:
   - The action (specific: who to contact, what to say, when)
   - Why it's high-leverage RIGHT NOW (timing, political dynamics)
   - Estimated effort (e.g., "4 minutes" or "2 hours including travel to City Hall")
   - Alternatives at different effort levels
   - For communications: pre-drafted text + contact info
   - [Take action →] link to web console with draft pre-loaded

3. FURTHER READING (optional)
   [2-3 links for the curious]

4. FOOTER
   - "Was this useful?" quick reaction link
   - Link to web console for follow-up questions
   - Manage preferences link
   - Unsubscribe
```

### Design Notes
- Target: readable in 5 minutes
- Monday morning delivery (configurable later)
- Some weeks the honest answer is "quiet week" — never pad with filler
- Email links back to web console for deeper engagement

---

## 7. Tech Stack Details

```
Frontend:      Next.js 14+ on Vercel
Auth:          Clerk or Supabase Auth
Database:      Supabase (Postgres + Row Level Security)
Chat UI:       Vercel AI SDK (@ai-sdk/anthropic for streaming)
Email:         Resend (or SES)
Payments:      Stripe (checkout + customer portal)
Scheduling:    GitHub Actions (Phase 0-1) → BullMQ on Redis or similar at scale
LLM:           Anthropic Claude API
               - claude-haiku-4-5-20251001 for classification
               - claude-sonnet-4-5-20250514 for digest generation + reasoning
Data ingest:   Python 3.11+
               - feedparser (RSS)
               - requests / httpx (HTTP)
               - python-legistar-scraper (Legistar)
               - supabase-py (database)
Deployment:    Vercel (web) + Fly.io or Railway (Python pipeline jobs)
```

### Key Dependencies to Install
```bash
# Python pipeline
pip install feedparser httpx supabase anthropic

# Node.js web app
npx create-next-app@latest ubl-web
npm install @clerk/nextjs @supabase/supabase-js @ai-sdk/anthropic ai stripe resend
```

---

## 8. Database Schema (Starting Point)

```sql
-- Users
create table users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  district text,
  voter_registered boolean,
  preferences jsonb default '{}',  -- fault line responses, free text, engagement prefs
  preference_history jsonb default '[]',  -- reactive preference signals over time
  engagement_prefs jsonb default '{}',  -- time budget, in-person willingness, financial comfort
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Ingested articles
create table articles (
  id uuid primary key default gen_random_uuid(),
  source text not null,  -- 'mission_local', 'sfgate', 'legistar', etc.
  title text not null,
  url text unique,
  content text,  -- full text or summary depending on source
  published_at timestamptz,
  topics text[],  -- ['housing', 'transit', 'public_safety']
  relevance_tags jsonb default '{}',  -- Haiku classification output
  is_time_sensitive boolean default false,
  deadline timestamptz,  -- if time-sensitive, when does the window close
  created_at timestamptz default now()
);

-- Generated digests
create table digests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  week_of date not null,  -- Monday of the digest week
  content jsonb not null,  -- structured digest content
  email_sent_at timestamptz,
  email_opened boolean default false,
  created_at timestamptz default now()
);

-- User reactions to digest items (preference learning)
create table reactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  digest_id uuid references digests(id),
  article_id uuid references articles(id),
  reaction text not null,  -- 'more', 'less', 'thoughts'
  comment text,  -- free text if reaction = 'thoughts'
  created_at timestamptz default now()
);

-- Conversation history (web console follow-ups)
create table conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  messages jsonb not null default '[]',  -- [{role, content, timestamp}]
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Row Level Security: users can only access their own data
alter table users enable row level security;
alter table digests enable row level security;
alter table reactions enable row level security;
alter table conversations enable row level security;
```

---

## 9. What Not to Build (MVP Scope Boundaries)

- **No mobile app.** Web + email only.
- **No real-time alerts in MVP.** Weekly digest only. Tag time-sensitive items in the pipeline for future use.
- **No automated email sending.** The system drafts emails; the user copies and sends. Never send on the user's behalf.
- **No automated state-level data ingestion in MVP.** No leginfo API, no CalMatters RSS, no Sacramento bill tracking pipeline. However, the conversational follow-up and digest generation should use the model's base knowledge to identify when an issue is state-controlled (rent regulation, school funding, MTA, etc.), explain the jurisdictional reality, offer to draft communications to state representatives, and be honest about the lower expected leverage at that level. This is system prompt guidance, not engineering work. See Section 4 for prompt instructions.
- **No social features.** No sharing, no community, no "see what your neighbors are doing." Individual product.
- **No admin dashboard in MVP.** Monitor via Supabase dashboard and email analytics directly.
- **Don't over-engineer the pipeline.** If an RSS feed breaks, fix it manually. Don't build auto-recovery or failover for 10 data sources.
- **Don't build a custom email editor.** Use pre-drafted text that users copy. Rich editing comes later if ever.

---

## 10. Code Quality & Maintainability

This project will be vibecoded initially and may later have other people working on it. Vibecoded projects have a specific failure mode: everything works, but nobody (including you in 3 months) can understand *why* it works or safely change it. These guidelines prevent that.

### For Claude Code: Follow These Rules

**Structure and separation of concerns:**
- Keep the project structure from Section 2 (`/pipeline`, `/digest`, `/delivery`, `/web`, `/jobs`). Don't let modules bleed into each other. The pipeline should know nothing about the web app. The web app should know nothing about how digests are generated.
- Each file should do one thing. `ingest.py` fetches articles. `classify.py` classifies them. `store.py` writes to the database. Don't combine steps into monolithic scripts.
- Keep shared configuration (API keys, model IDs, Supabase URL, source list) in a single config file or environment variables, never hardcoded in multiple places.

**Naming and readability:**
- Use descriptive function and variable names. `classify_article(article, topics)` not `process(a, t)`.
- Name files for what they do, not for when they were created or which phase they belong to.
- If a function is longer than ~40 lines, it's probably doing too many things. Break it up.

**Comments and documentation:**
- Every file gets a docstring at the top explaining what it does and how it fits into the pipeline. One or two sentences is enough.
- Every function gets a docstring explaining inputs, outputs, and any non-obvious behavior.
- Don't comment obvious code. Do comment *why* decisions were made, especially: why a particular model is used for a task, why data is structured a certain way, why a particular prompt instruction exists.
- System prompts and prompt templates should live in clearly labeled files (e.g., `prompts/digest_system.txt`, `prompts/leverage_assessment.txt`), not inline as string literals in Python code. This makes them easy to find, read, and iterate on without touching code.

**Prompt management:**
- All prompts in a `/prompts` directory as separate text/markdown files.
- Each prompt file should have a header comment explaining: what it's for, which model it's used with, what inputs it expects, and what output format it produces.
- Version prompt files meaningfully — if you make a major change to the leverage assessment prompt, note what changed and why (a comment at the top of the file is fine).
- The political context document should be a separate file (`prompts/sf_political_context.md`) that can be updated independently of the code.

**Type hints and validation:**
- Use Python type hints on all function signatures. This is the single most helpful thing for someone reading vibecoded Python later.
- Use Pydantic models or TypedDicts for structured data that flows between modules (article objects, user profiles, digest content). Don't pass raw dicts with undocumented keys.
- TypeScript strict mode in the Next.js app. Vibecoded TypeScript without strict mode becomes unreadable fast.

**Error handling:**
- The pipeline will break. RSS feeds change, APIs go down, the LLM returns unexpected output. Every external call (HTTP fetch, API call, DB write) should have try/except with logging. Don't let one broken RSS feed crash the entire ingestion run.
- Log errors with enough context to debug: which source failed, what the input was, what the error was. Use Python's `logging` module, not print statements.
- For the digest generation pipeline: if a single user's digest fails, log it and continue to the next user. Don't abort the batch.

**Testing:**
- Don't need comprehensive test coverage for MVP. But do have:
  - A smoke test for the ingestion pipeline: "does it fetch from at least 3 sources without crashing"
  - A smoke test for digest generation: "given these 10 sample articles and this user profile, does it return valid structured output"
  - A way to run the full pipeline locally for a single test user without sending an actual email (dry run mode)
- Store 2-3 example article sets and user profiles as test fixtures. This lets you iterate on prompts and immediately see the output without waiting for a real ingestion run.

**Git hygiene:**
- Meaningful commit messages. "Fix digest generation" is useless. "Fix: leverage assessment was ignoring user's district when recommending actions" is useful.
- Don't commit API keys, `.env` files, or the political context document (it contains editorial judgments that should be managed separately). Use `.env.example` with placeholder values.
- Keep a `CHANGELOG.md` with dated entries for significant changes. This is the first thing a new contributor reads.

**Dependency management:**
- `requirements.txt` (Python) and `package.json` (Node) with pinned versions. Vibecoded projects are especially vulnerable to breaking when a dependency updates.
- Keep dependencies minimal. Every library you add is a library someone has to understand later.

### README.md

The repo should have a README that covers:
1. What this project is (2 sentences)
2. How to set up a local development environment (step by step)
3. How to run the pipeline locally (single user dry run)
4. How to deploy
5. Where the prompts live and how to edit them
6. Where the political context document lives and how to update it
7. Architecture overview pointing to the relevant source directories

This README is the first thing a new contributor (or future-you) reads. Keep it current.
