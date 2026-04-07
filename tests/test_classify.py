"""Tests for article classification. Hits the Anthropic API with sample articles.

Tests that require ANTHROPIC_API_KEY are skipped if the key is not set.
"""

import json
from pathlib import Path

import pytest

from ubl.config import get_settings
from ubl.models import RawArticle
from ubl.pipeline.classify import classify_article, classify_articles

FIXTURES_DIR = Path(__file__).parent / "fixtures"

needs_api_key = pytest.mark.skipif(
    not get_settings().anthropic_api_key,
    reason="ANTHROPIC_API_KEY not set",
)


def _load_sample_articles() -> list[RawArticle]:
    with open(FIXTURES_DIR / "sample_articles.json") as f:
        data = json.load(f)
    return [RawArticle(**article) for article in data]


@pytest.fixture
def sample_articles() -> list[RawArticle]:
    return _load_sample_articles()


@needs_api_key
def test_classify_single_housing_article(sample_articles):
    """The fourplex rezoning article should be classified as housing."""
    housing_article = sample_articles[0]  # "Board of Supervisors to vote on fourplex rezoning"
    result = classify_article(housing_article)

    assert "housing" in result.topics
    assert result.relevance_score >= 0.7
    assert result.summary
    assert result.is_time_sensitive is True


@needs_api_key
def test_classify_sports_article_low_relevance(sample_articles):
    """A sports article should get a low civic relevance score."""
    sports_article = sample_articles[4]  # "Warriors fall to Lakers"
    result = classify_article(sports_article)

    assert result.relevance_score <= 0.3


@needs_api_key
def test_classify_batch(sample_articles):
    """Classify all sample articles and verify basic structure."""
    results = classify_articles(sample_articles[:3], delay=0.1)

    assert len(results) == 3
    for result in results:
        assert result.topics
        assert 0.0 <= result.relevance_score <= 1.0
        assert result.url
