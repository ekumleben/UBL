"""Tests for digest generation. Hits the Anthropic API with sample data."""

import json
from pathlib import Path

import pytest

from ubl.config import PROMPTS_DIR
from ubl.models import ClassifiedArticle, UserProfile
from ubl.digest.generate import generate_digest, _filter_relevant_articles

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_user() -> UserProfile:
    with open(FIXTURES_DIR / "sample_user_profile.json") as f:
        return UserProfile(**json.load(f))


def _load_classified_articles() -> list[ClassifiedArticle]:
    """Create pre-classified articles for testing (bypasses Haiku classification)."""
    return [
        ClassifiedArticle(
            source="mission_local",
            title="Board of Supervisors to vote on fourplex rezoning proposal Thursday",
            url="https://example.com/fourplex-rezoning",
            content="The SF Board of Supervisors will vote Thursday on fourplexes in single-family zones.",
            published_at="2026-04-02T10:00:00Z",
            topics=["housing"],
            relevance_score=0.95,
            summary="Board votes Thursday on fourplex rezoning. Key housing density decision.",
            is_time_sensitive=True,
            deadline="2026-04-04",
        ),
        ClassifiedArticle(
            source="streetsblog_sf",
            title="SFMTA approves new protected bike lane on Valencia Street",
            url="https://example.com/valencia-bike-lane",
            content="SFMTA Board voted 5-2 to approve Valencia protected bike lane.",
            published_at="2026-04-01T15:30:00Z",
            topics=["transit"],
            relevance_score=0.8,
            summary="SFMTA approved Valencia bike lane. Construction starts June.",
            is_time_sensitive=False,
        ),
        ClassifiedArticle(
            source="sf_standard",
            title="SF homelessness count shows 5% decrease",
            url="https://example.com/homeless-count",
            content="Biennial count shows 7,400 unhoused individuals, down 5%.",
            published_at="2026-03-30T08:00:00Z",
            topics=["homelessness"],
            relevance_score=0.7,
            summary="Homeless count down 5%. Officials cite expanded shelter capacity.",
            is_time_sensitive=False,
        ),
    ]


def test_filter_relevant_articles():
    """Filtering prioritizes user's topics and time-sensitive items."""
    user = _load_user()
    articles = _load_classified_articles()

    filtered = _filter_relevant_articles(articles, user)

    assert len(filtered) > 0
    # Housing article should rank high (user agrees on housing + time-sensitive)
    assert filtered[0].topics == ["housing"]


def test_generate_digest_with_api():
    """Generate a real digest using the Anthropic API.

    This test requires ANTHROPIC_API_KEY to be set. It will be skipped
    if the key is not available.
    """
    from ubl.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    user = _load_user()
    articles = _load_classified_articles()

    context_file = PROMPTS_DIR / "sf_political_context.md"
    if context_file.exists():
        political_context = context_file.read_text()
    else:
        political_context = "No political context available for testing."

    digest = generate_digest(user, articles, political_context)

    assert digest.user_id == "test-user-001"
    assert len(digest.items) >= 1
    for item in digest.items:
        assert item.headline
        assert item.summary
