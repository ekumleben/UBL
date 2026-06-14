"""Ingestion pipeline orchestrator. Fetches, classifies, and stores articles.

Usage:
    python -m ubl.pipeline.run
"""

from __future__ import annotations

import logging
import time

from ubl.logging_config import setup_logging
from ubl.pipeline.campaign_finance import fetch_campaign_finance
from ubl.pipeline.classify import classify_articles
from ubl.pipeline.ingest import fetch_all_feeds
from ubl.pipeline.meetings import fetch_upcoming_meetings
from ubl.pipeline.store import get_stored_urls, store_articles
from ubl.pipeline.transcripts import fetch_recent_transcripts

logger = logging.getLogger(__name__)


def run_ingestion_pipeline() -> int:
    """Run the full ingestion pipeline: fetch → deduplicate → classify → store.

    Returns:
        Number of new articles stored.
    """
    start = time.time()

    # 1. Fetch from all sources
    logger.info("Starting ingestion pipeline")
    raw_articles = fetch_all_feeds()
    meetings = fetch_upcoming_meetings()
    raw_articles.extend(meetings)
    # Auto-target the next upcoming SF election
    from datetime import date
    today = date.today()
    sf_elections = [
        "2026-11-03",  # November general
        "2027-06-01",  # June (placeholder — update when date confirmed)
    ]
    next_election = None
    for ed in sf_elections:
        if date.fromisoformat(ed) >= today:
            next_election = ed
            break
    finance = fetch_campaign_finance(election_date=next_election)
    raw_articles.extend(finance)
    transcripts = fetch_recent_transcripts(max_per_body=2)
    raw_articles.extend(transcripts)
    if not raw_articles:
        logger.warning("No articles fetched from any source")
        return 0

    # 2. Filter out articles already in the database
    urls = [a.url for a in raw_articles]
    existing_urls = get_stored_urls(urls)
    new_articles = [a for a in raw_articles if a.url not in existing_urls]

    logger.info(
        "Fetched %d articles, %d already stored, %d new",
        len(raw_articles),
        len(existing_urls),
        len(new_articles),
    )

    if not new_articles:
        logger.info("No new articles to classify")
        return 0

    # 3. Classify new articles
    classified = classify_articles(new_articles)

    # 4. Store in database
    stored = store_articles(classified)

    elapsed = time.time() - start
    logger.info(
        "Ingestion complete: %d new articles stored in %.1fs", stored, elapsed
    )
    return stored


if __name__ == "__main__":
    setup_logging()
    run_ingestion_pipeline()
