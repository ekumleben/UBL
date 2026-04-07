"""RSS feed ingestion. Fetches articles from configured feeds and returns RawArticle objects.

Each feed is fetched independently. Failures are logged and skipped so one
broken feed doesn't crash the entire ingestion run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from ubl.models import FeedSource, RawArticle

logger = logging.getLogger(__name__)


def _parse_published(entry: dict) -> datetime | None:
    """Extract a timezone-aware published datetime from a feedparser entry."""
    for field in ("published", "updated"):
        raw = entry.get(field)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass

    # feedparser sometimes parses dates into a time struct
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    return None


def _extract_content(entry: dict, full_text: bool) -> str | None:
    """Extract the best available article text from a feedparser entry.

    For full_text feeds, prefer the 'content' field (which contains the full
    article body in RSS). For summary-only feeds, use the 'summary' field.
    """
    if full_text:
        # feedparser stores full content in entry.content[0].value
        content_list = entry.get("content", [])
        if content_list:
            return content_list[0].get("value", "")

    # Fall back to summary
    return entry.get("summary") or entry.get("description")


def fetch_feed(source: FeedSource) -> list[RawArticle]:
    """Fetch and parse a single RSS feed.

    Args:
        source: The feed source configuration.

    Returns:
        List of RawArticle objects. Empty list on failure.
    """
    try:
        feed = feedparser.parse(source.url)

        if feed.bozo and not feed.entries:
            logger.warning(
                "Feed %s returned an error: %s", source.name, feed.bozo_exception
            )
            return []

        articles = []
        for entry in feed.entries:
            url = entry.get("link")
            title = entry.get("title")
            if not url or not title:
                continue

            articles.append(
                RawArticle(
                    source=source.name,
                    title=title.strip(),
                    url=url.strip(),
                    content=_extract_content(entry, source.full_text),
                    published_at=_parse_published(entry),
                )
            )

        logger.info("Fetched %d articles from %s", len(articles), source.name)
        return articles

    except Exception:
        logger.exception("Failed to fetch feed: %s (%s)", source.name, source.url)
        return []


def fetch_all_feeds(
    sources: list[FeedSource] | None = None,
) -> list[RawArticle]:
    """Fetch articles from all configured RSS feeds.

    Args:
        sources: Feed sources to fetch. Defaults to all configured feeds.

    Returns:
        Deduplicated list of RawArticle objects sorted by published_at descending.
    """
    if sources is None:
        from ubl.config import get_settings

        sources = get_settings().feeds

    all_articles: list[RawArticle] = []
    for source in sources:
        articles = fetch_feed(source)
        all_articles.extend(articles)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique: list[RawArticle] = []
    for article in all_articles:
        if article.url not in seen_urls:
            seen_urls.add(article.url)
            unique.append(article)

    # Sort by published_at descending (None values last)
    unique.sort(
        key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    logger.info(
        "Total: %d unique articles from %d feeds", len(unique), len(sources)
    )
    return unique
