"""Smoke tests for RSS ingestion. Hits real feeds to verify they're accessible."""

from ubl.models import FeedSource
from ubl.pipeline.ingest import fetch_all_feeds, fetch_feed

# The three critical, free, full-text feeds
CRITICAL_FEEDS = [
    FeedSource(name="mission_local", url="https://missionlocal.org/feed", priority="critical", full_text=True),
    FeedSource(name="48_hills", url="https://48hills.org/feed", priority="critical", full_text=True),
    FeedSource(name="streetsblog_sf", url="https://sf.streetsblog.org/feed", priority="critical", full_text=True),
]


def test_fetch_single_feed():
    """A single critical feed returns at least one article."""
    articles = fetch_feed(CRITICAL_FEEDS[0])
    assert len(articles) > 0
    article = articles[0]
    assert article.title
    assert article.url
    assert article.source == "mission_local"


def test_fetch_all_critical_feeds():
    """Fetching all three critical feeds returns a reasonable number of articles."""
    articles = fetch_all_feeds(CRITICAL_FEEDS)
    assert len(articles) >= 3, f"Expected at least 3 articles, got {len(articles)}"

    # All should have titles and URLs
    for article in articles:
        assert article.title
        assert article.url


def test_deduplication():
    """Fetching the same feed twice doesn't produce duplicates."""
    single = [CRITICAL_FEEDS[0]]
    articles = fetch_all_feeds(single + single)
    urls = [a.url for a in articles]
    assert len(urls) == len(set(urls)), "Duplicate URLs found"
