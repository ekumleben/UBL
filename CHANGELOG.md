# Changelog

## 2026-04-04 — Phase 0 MVP

Initial implementation of the UBL pipeline:

- **Ingestion:** RSS feed fetching from 9 SF news sources (Mission Local, 48 Hills, Streetsblog SF, SFGate, SF Standard, SFist, GrowSF)
- **Classification:** Haiku 4.5 article classification by topic, civic relevance, and time-sensitivity
- **Digest generation:** Sonnet 4.5 personalized weekly digest with news summaries
- **Leverage assessment:** Sonnet 4.5 + extended thinking for high-leverage civic action recommendations
- **Action drafting:** Sonnet 4.5 drafts emails and public comments
- **Email delivery:** Jinja2 HTML templates + Resend for sending
- **Scheduling:** GitHub Actions weekly cron + manual trigger
- **Database:** Supabase schema for articles, users, digests, reactions, conversations
