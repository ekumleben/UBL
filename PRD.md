# Universal Basic Lobbyist — Product Requirements Document

**Version:** 0.1 (Draft)
**Author:** Emma
**Date:** March 2026
**Status:** Pre-build

---

## 1. Overview

Universal Basic Lobbyist (UBL) is an AI-powered civic engagement assistant for individual citizens in relation to their local government. The system monitors local government activity, news coverage, and civic advocacy with the user's concerns in mind; provides tailored updates; advises on the highest-leverage opportunities to intervene; and reduces friction by drafting communications and providing contact information.

**Core value proposition:** Lobbying is the most effective form of political participation, and it's almost entirely unavailable to individual citizens — not because the actions are gated, but because the intelligence about which actions matter is concentrated among expensive professionals. UBL collapses that information asymmetry.

**Brand positioning:** "Your personal lobbyist for $10/month." The name makes an explicit political argument: lobbying access should not be wealth-gated. The product should deliver on this promise with genuine, personalized, high-quality civic intelligence — not generic calls to action.

---

## 2. Target User

**Primary persona:** Busy professional in San Francisco (25-45) who cares about local issues but doesn't follow local government, doesn't know their supervisor, and has ~20 minutes per week of engagement budget. They want outcomes (housing gets built, streets get cleaner, schools improve) and feel vague guilt about not being more engaged. They are not ideologically committed to a specific political framework but have intuitions and preferences on specific issues.

**Not the target (initially):** Already-engaged civic activists, advocacy organizations, political professionals. These users may come later as the product evolves.

---

## 3. Business Model

- **Pricing:** $9.99/month, all-paid, no free tier.
- **Trial:** 2-week trial with card upfront, or money-back first month. TBD on specifics.
- **Rationale for no free tier:** Every user is a real signal of demand. Simplifies everything — no conversion funnel, no free users consuming API costs. Filters for people who genuinely value the product.
- **Unit economics:** Blended API cost ~$0.90-1.50/user/month (optimized). ~$8-9 gross margin per user. Profitable at modest scale (~200+ paying users).
- **Revenue target:** 500 paying users = ~$5K/month. 1,000 users = ~$10K/month. This is a bootstrapped side project, not a venture-scale business (see Section 12 for future expansion discussion).

---

## 4. Product Architecture

### 4.1 System Components

1. **Data ingestion pipeline** (shared, runs daily)
   - Fetches from RSS feeds, Legistar API, government sources
   - Classifies and tags articles by topic, relevance, urgency
   - Model: Haiku 4.5 (cheap, fast)

2. **Personalized digest generation** (per-user, runs weekly)
   - Matches ingested content against user preference profile
   - Generates weekly digest with summaries and context
   - Model: Sonnet 4.5 via Batch API (quality writing at batch discount)

3. **Leverage assessment engine** (per-user, runs weekly)
   - Reasons about timing, political dynamics, user's district, available actions
   - Identifies 1-3 highest-leverage actions for the week
   - Model: Sonnet 4.5 with extended thinking (needs genuine reasoning about political strategy)

4. **Action drafting** (per-user, on-demand)
   - Drafts specific emails, public comments, testimony
   - Pre-fills recipient contact information
   - Model: Sonnet 4.5

5. **Conversational follow-up** (per-user, on-demand via web console)
   - Users can ask questions, go deeper on issues, request alternative actions
   - Model: Haiku 4.5 for factual lookups, Sonnet 4.5 for substantive questions, Sonnet with thinking for strategic advice

### 4.2 Delivery Channels

- **Primary:** Weekly email digest (push), delivered Monday morning
- **Secondary:** Web console (pull) for follow-up conversations, preferences, account management
- **Future (post-MVP):** Time-sensitive alerts for items with deadlines in the next 48 hours

### 4.3 Technical Stack (Anticipated)

- **Frontend:** Next.js on Vercel
- **Auth:** Clerk or Supabase Auth
- **Database:** Supabase (Postgres)
- **Chat UI:** Vercel AI SDK (streaming)
- **Email delivery:** Resend or SES
- **Payments:** Stripe
- **Scheduling:** GitHub Actions (MVP) → proper job queue at scale
- **LLM:** Anthropic Claude API (Haiku 4.5, Sonnet 4.5)
- **Data ingestion:** Python scripts (feedparser, requests, Python Legistar Scraper)

---

## 5. Data Sources

### 5.1 Government (Critical)

| Source | Access Method | Priority |
|--------|-------------|----------|
| SF Board of Supervisors (Legistar) | API — Python Legistar Scraper | Critical |
| Committee calendars/agendas | Via Legistar | Critical |
| Mayor's Office press releases | Web scrape | High |
| SF Planning Commission | Web scrape (PDFs) | High (for housing/land use) |
| DataSF (Open Data Portal) | Socrata API (SODA) | Medium (background context) |

### 5.2 News Media

| Source | Access | Paywall | Priority |
|--------|--------|---------|----------|
| Mission Local | RSS (missionlocal.org/feed) — full text | Free | Critical |
| SFGate | RSS (section feeds) — free | Free | High |
| SF Standard | RSS (sfstandard.com/feed, section feeds) — summaries only | Metered ($9/mo for full text) | High |
| 48 Hills | RSS (48hills.org/feed) — full text | Free | High |
| Streetsblog SF | RSS (sf.streetsblog.org/feed) | Free | High (transit/streets) |
| KQED Politics | RSS (kqed.org/politics) | Free | Medium-High |
| SF Examiner | RSS | Free | Medium |
| The Frisc | Newsletter / scrape | Free | Medium |
| SFist | RSS (sfist.com/rss) | Free | Low |

### 5.3 Advocacy & Civic Organizations

| Source | Access | Lean | Priority |
|--------|--------|------|----------|
| GrowSF | Substack RSS (report.growsf.org) | Moderate-reformist | High |
| SFYIMBY | Blog/email — scrape or manual | Pro-housing | High (housing) |
| TogetherSF Action | Newsletter — email parse or scrape | Moderate-reformist | Medium-High |
| SPUR | Blog/newsletter | Urbanist-centrist | Medium |
| SF Housing Action Coalition | Newsletter | Pro-housing | Medium |
| Coalition for SF Neighborhoods | Minimal web presence | Preservationist/NIMBY | Medium (opposition monitoring) |
| SF Transit Riders | Newsletter | Pro-transit | Medium (transit) |

See separate source audit spreadsheet for full details including RSS URLs, paywall status, and accessibility ratings.

---

## 6. User Experience

### 6.1 Onboarding

**Design principle:** Progressive disclosure. Fast path for "just tell me what to do" users, depth available for those with strong opinions.

**Layer 1: Core preference elicitation (60 seconds)**
- 5-8 agree/disagree/skip statements on SF's key political fault lines:
  - Housing density: "The city should make it easier to build apartment buildings"
  - Street conditions: "The city's approach to homelessness should prioritize treatment and shelter over harm reduction"
  - Transit: "The city should prioritize public transit and bike lanes over car infrastructure"
  - Government reform: "City government needs structural reform to be more accountable"
  - Public safety: "The city needs stricter enforcement of quality-of-life laws"
  - Education: "SFUSD needs significant reform, even if that means controversial changes like school closures"
- These are framed as plain-language statements, not policy jargon. The user doesn't need to understand zoning law to react to "the city should make it easier to build apartment buildings."
- "Skip" is always an option and is treated as a weak prior, not an absence of signal.

**Layer 2: Optional depth (per-question)**
- After each response, an optional "tell me more" expansion
- Either follow-up questions that get more specific, or a free text box
- "You said agree on building more housing — anything specific? (skip if not)"
- Most users skip. The user who types "I'm fine with density but the 469 Stevenson project was a disaster" gives a much richer signal.

**Layer 3: Ongoing calibration**
- System occasionally surfaces a preference-clarifying question inline with weekly digest
- "We recommended X, was that the kind of thing you want to see?" (low-friction yes/no/not relevant)
- Click/engagement behavior refines preferences over time (see Section 10 on privacy)

**Additional intake:**
- District (auto-detect from address or zip, confirm)
- Voter registration status
- Engagement preferences: time budget per week, willingness to attend in-person events, financial engagement comfort level

### 6.2 Weekly Digest (Email)

The weekly digest is the core product. It should feel like a smart, concise briefing from someone who's been paying attention on your behalf.

**Structure:**
1. **What happened this week** (3-5 items, ranked by relevance to user's priorities)
   - For each: 2-3 sentence summary, why it matters for the user specifically, link to source
2. **Recommended actions** (1-3, ranked by leverage)
   - For each: the action, why it's high-leverage *right now*, estimated time/effort, alternatives
   - For communications: pre-drafted text + recipient contact info
   - Transparency: explain the rationale, present alternative actions and perspectives
3. **Further reading** (2-3 links for the curious, optional)
4. **Quick preference check** (optional, inline): "Was this digest relevant to you?" or a specific preference question

**Design principles:**
- Concise. The entire digest should be readable in 5 minutes.
- Specific. "Email Supervisor Chan about the fourplex rezoning vote on Thursday" not "consider reaching out to your elected officials about housing."
- Honest about uncertainty. If the leverage assessment is uncertain, say so. "This might matter, but we're not sure how close the vote will be."
- Never generate filler. Some weeks nothing high-leverage is happening. The honest answer is "quiet week, here's some background reading" not a padded digest that erodes trust.

### 6.3 Web Console

Accessible via link in email digest. The web app is where users:
- **Ask follow-up questions:** conversational interface for going deeper on any issue in the digest or any SF civic topic
- **Manage preferences:** update priority areas, engagement constraints, contact info
- **View history:** past digests, past recommendations, what actions they took
- **Manage account:** billing, notification preferences

The chat interface should have context from the user's latest digest and preference profile. When a user asks "tell me more about the rezoning proposal," the system already knows which proposal and what the user's stance is likely to be.

### 6.4 Action Recommendations

**Full menu of possible action types — all are available. System recommends based on leverage assessment and user engagement preferences.**

- Email/call an elected official (supervisor, mayor, state rep)
- Submit written public comment for a hearing
- Attend a hearing in person / provide in-person testimony
- Sign a petition or open letter
- Join an advocacy group's specific call to action (e.g., SFYIMBY letter campaign)
- Attend a rally, community meeting, or civic event
- Donate to a campaign or advocacy organization
- Contact a specific city agency or commission
- Vote (in elections, or inform voting decisions via voter guide-style information)

**Design principle for all recommendations: show your work.**

Every recommendation comes with:
- The action and specific logistics (who, where, when, how)
- Why it's high-leverage right now (timing, political dynamics, the user's specific position)
- What it costs the user (time, money, social exposure, political visibility)
- Alternative actions at different effort levels
- Relevant context the user should know before acting
- For politically charged actions (donations, endorsements, partisan events): explicit labeling of what kind of action this is, transparency about the political nature, relevant positions of all parties involved

**The system never makes a recommendation without explaining the rationale and offering alternatives.** This is what distinguishes it from an advocacy organization pushing an agenda — the user is always the decision-maker.

---

## 7. Leverage Assessment

The leverage assessment is the core intellectual challenge and the main differentiator. This is the "lobbyist brain."

### 7.1 What Makes an Action "High Leverage"

Factors the system should consider:
- **Timing:** Is there an upcoming vote, hearing, or deadline? Is the window closing?
- **Marginal impact:** Is the outcome genuinely uncertain? Is the user's input decision-relevant? (A constituent email on a 10-1 vote is low leverage; on a 6-5 vote where your supervisor is undecided, it's high leverage.)
- **District relevance:** Is the user a constituent of a key decision-maker on this issue?
- **Specificity of ask:** Is there a concrete, specific thing to ask for? ("Vote yes on item 12" vs. "please care about housing")
- **Channel match:** Is the recommended channel (email, hearing, public comment) the one most likely to be noticed for this issue?
- **User fit:** Does this match the user's engagement preferences and constraints?

### 7.2 Political Context

The system needs a maintained political context document (part of the system prompt or knowledge base) containing:
- Current Board of Supervisors composition, districts, committee assignments
- Current political coalitions and alliances
- Known positions of supervisors on key issues
- Upcoming election context (who's termed out, who's running, who's vulnerable)
- Recent major policy developments and their trajectory

**This document requires manual maintenance.** It should be updated at minimum monthly, more frequently during politically active periods. This is the primary ongoing operational cost of the product and cannot be fully automated — it requires editorial judgment about SF politics.

### 7.3 Expert Knowledge Integration (Future)

To improve leverage assessments over time, incorporate condensed insights from structured interviews with people who understand SF civic engagement from the inside: former/current staffers, lobbyists, advocacy leaders, journalists. These interviews would be synthesized into structured guidance for the system — "what kinds of civic engagement actually sway decisions, and what is engagement theater that feels good but doesn't change outcomes."

---

## 8. Build Plan

### Phase 0: Personal MVP (Week 1-2)

**Goal:** Validate that the AI reasoning about civic leverage is useful for a single user (yourself).

- Build data ingestion pipeline (RSS feeds + Legistar scraping)
- Write system prompt with your priorities and SF political context
- Generate weekly digest via Claude API
- Deliver via email (Resend)
- Scheduling via GitHub Actions
- **Output:** A weekly email you look forward to reading. If the recommendations feel generic or wrong, stop here and iterate on the prompt before building anything else.

### Phase 1: Shareable MVP (Week 3-6)

**Goal:** Launch to paying users in SF.

- Web app scaffold (Next.js / Vercel)
- Auth (Clerk or Supabase)
- Onboarding flow with preference elicitation
- Per-user digest personalization
- Web console with conversational follow-up (Vercel AI SDK, streaming)
- Email digest templates + delivery
- Stripe billing ($9.99/month, trial period TBD)
- Landing page at universalbasiclobbyist.ai
- **Output:** A product people pay for. Target: 50-100 paying users within first month via personal network and SF civic tech / tech community distribution.

### Phase 2: Quality & Retention (Month 2-4)

**Goal:** Prove retention. Users who signed up in Month 1 are still opening the digest in Month 3.

- Monitor engagement (open rates, click rates, cancellation patterns)
- Tune system prompt and political context based on user feedback
- Add preference calibration via inline digest questions
- Improve action drafting quality (more specific, better personalized)
- Begin tagging time-sensitive items in pipeline for future alerts
- Begin user interviews to understand what's working and what's not
- **Output:** Retention data, NPS or equivalent, clear signal on product-market fit.

### Phase 3: Feature Expansion (Month 4-6)

**Goal:** Fill out the product based on learned user needs.

- Time-sensitive alerts (email notifications for deadlines within 48 hours)
- Richer action history and tracking in web console
- Voter guide-style information for upcoming elections
- California state-level monitoring integration (leginfo API, CalMatters, etc.)
- Expert knowledge integration from structured interviews
- **Output:** A more complete product that justifies the $9.99/month indefinitely.

---

## 9. Success Metrics

### MVP (Month 1)

- Number of paying users at end of month 1
- Digest email open rate (target: >60%)
- At least 1 user takes a recommended action per week (self-reported or inferred from click-through)

### Retention (Month 3)

- Month-over-month retention rate (target: >70%)
- Weekly digest open rate sustained above 50%
- Cancellation survey responses (why people leave)

### Scale (Month 6)

- Total paying users (target: 500)
- Monthly revenue (target: ~$5K)
- Cost per user (target: <$1.50)
- At least one concrete example of a recommendation leading to a measurable civic outcome

---

## 10. Privacy & Data Ethics

### Principles

UBL handles political preference and engagement data, which is sensitive. The product's brand is built on democratizing power, so being cavalier with user data would be reputationally catastrophic.

### Data Handling

- **Aggregate analytics (default):** Email open rates and click-through rates at the aggregate level. Standard for email products, covered by a standard privacy policy.
- **Per-user preference learning (opt-in):** Engagement patterns used to refine future digests. Users are told explicitly during onboarding: "We use your engagement to personalize your digest. You can turn this off anytime."
- **Data never shared or sold.** No exceptions, no "anonymized" data sharing, no partnerships that involve user behavior data.
- **User data export and deletion:** Users can export their full data and delete their account at any time. Deletion is real deletion, not soft-delete.
- **No tracking of post-email actions.** The system does not track whether users actually sent a recommended email or attended a hearing. This would require invasive integration with email clients or self-reporting that adds friction.

### Privacy Policy

A short, plain-English privacy page. Not legal boilerplate — a readable explanation of what data is collected, what it's used for, and what is never done with it. This is itself a brand differentiator for a civic engagement tool.

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Recommendations feel generic / low quality | High | Invest heavily in system prompt, political context, and ongoing tuning. This is the #1 operational priority. |
| Low retention after initial signup | High | Weekly quality monitoring, user interviews, preference calibration. No-filler policy — honest "quiet week" digests. |
| Data pipeline breaks (RSS changes, Legistar updates) | Medium | Monitoring/alerting. Budget 2-3 hours/month for maintenance. |
| Political context goes stale | Medium | Monthly review minimum. Set calendar reminders. Biggest risk during elections and Board turnover. |
| AI-generated constituent emails get flagged/discounted by supervisor offices | Medium | Draft emails as starting points, not send-ready templates. Encourage personalization. Be transparent in product about this risk. |
| Privacy incident or perceived misuse of political data | High | Minimal data collection, no sharing/selling, clear privacy policy. Consider open-sourcing the recommendation engine for transparency. |
| User uses tool to engage in ways that are harmful or harassing | Low-Medium | Recommendations come with context and rationale. System does not automate sending — user always takes final action. Terms of service prohibit use for harassment. |
| Competitor or large platform builds similar tool | Low | The moat is not the technology (it's simple) — it's the maintained political context, the editorial quality, and the trust relationship with SF users. |

---

## 12. Future Considerations (Out of Scope for MVP)

These are directions the product could go but are explicitly deferred until the core product is validated.

- **California state-level integration:** Natural extension, same user, same political ecosystem. Bundled with SF subscription. (See conversation notes — this is likely the first expansion.)
- **Geographic expansion (NYC, other cities):** Different data pipeline per city, same architecture. Requires local political knowledge per city. Brooklyn + Manhattan as a likely second city if expansion is pursued.
- **Organizational tier:** Dashboard, multi-issue monitoring, team access, API. Same underlying data engine, different interface and price point ($200-500/month). Likely the bigger business opportunity long-term.
- **Open source:** Open source the pipeline architecture, run a paid hosted instance. Hybrid model — code is free, operational expertise costs money. Defer until architecture is proven.
- **Platform / data layer:** Structured legislative data, political relationship graphs, voting pattern analysis as an API for researchers, journalists, civic tech tools.

---

## 13. Open Questions

- **Trial structure:** 2-week free trial with card upfront, or money-back first month? Need to decide before launch.
- **Feedback mechanism:** Beyond aggregate email analytics, how to efficiently learn what users want without adding friction? In-digest thumbs up/down? Occasional 1-question surveys?
- **Expert interviews:** Who to interview first for the leverage assessment knowledge base? Former supervisor staffers? SF Chronicle City Hall reporter? GrowSF leadership?
- **Partisan boundary:** The product recommends all action types including donations and campaign activity, with full transparency. But does the product itself take editorial positions on candidates? Probably not — but this needs a clear policy before election season.
- **Name/branding for org product:** If/when the organizational tier launches, does it live under the UBL brand or get its own name? "Universal Basic Lobbyist for Organizations" is a mouthful.

---

*universalbasiclobbyist.ai*
