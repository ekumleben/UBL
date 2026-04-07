"""Digest generation using Sonnet 4.5.

Takes a user profile, classified articles, and political context to produce
a personalized weekly digest with news summaries and further reading.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import anthropic

from ubl.config import SONNET_MODEL, get_settings
from ubl.models import ClassifiedArticle, Digest, DigestItem, UserProfile
from ubl.pipeline.classify import load_prompt

logger = logging.getLogger(__name__)


def _filter_relevant_articles(
    articles: list[ClassifiedArticle],
    user: UserProfile,
    min_score: float = 0.3,
    max_articles: int = 20,
) -> list[ClassifiedArticle]:
    """Filter and rank articles by relevance to the user's preferences.

    Args:
        articles: Classified articles from the past week.
        user: The user's profile with preference data.
        min_score: Minimum relevance score to include.
        max_articles: Maximum articles to pass to the LLM.

    Returns:
        Filtered and sorted list of articles.
    """
    # Filter by minimum relevance score
    relevant = [a for a in articles if a.relevance_score >= min_score]

    # Boost articles matching user's preferred topics
    user_topics = set()
    prefs = user.preferences
    topic_map = {
        "housing_density": "housing",
        "transit_priority": "transit",
        "quality_of_life_enforcement": "public_safety",
        "homelessness_treatment": "homelessness",
        "education_reform": "education",
        "government_reform": "government_reform",
    }
    for pref_key, topic in topic_map.items():
        if prefs.get(pref_key) in ("agree", "disagree"):
            user_topics.add(topic)

    def sort_key(article: ClassifiedArticle) -> float:
        score = article.relevance_score
        # Boost if article topics overlap with user's interests
        if user_topics and set(article.topics) & user_topics:
            score += 0.2
        # Boost time-sensitive items
        if article.is_time_sensitive:
            score += 0.15
        return score

    relevant.sort(key=sort_key, reverse=True)
    return relevant[:max_articles]


def generate_digest(
    user: UserProfile,
    articles: list[ClassifiedArticle],
    political_context: str,
) -> Digest:
    """Generate a personalized weekly digest.

    Uses Sonnet 4.5 to select and summarize the most relevant articles for the
    user. Phase 0 uses the synchronous API; switch to Batch API for Phase 1.

    Args:
        user: The user's profile.
        articles: Classified articles from the past week.
        political_context: The SF political context document text.

    Returns:
        A Digest object with items and further reading.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    relevant = _filter_relevant_articles(articles, user)
    if not relevant:
        logger.warning("No relevant articles found for user %s", user.id)
        return Digest(user_id=user.id, week_of=date.today())

    system_prompt = load_prompt("digest_system.md")

    # Build the user message with all context
    articles_json = [
        {
            "url": a.url,
            "title": a.title,
            "source": a.source,
            "summary": a.summary,
            "topics": a.topics,
            "relevance_score": a.relevance_score,
            "is_time_sensitive": a.is_time_sensitive,
            "deadline": a.deadline.isoformat() if a.deadline else None,
            "content_preview": (a.content or "")[:500],
        }
        for a in relevant
    ]

    user_message = (
        f"## User Profile\n"
        f"District: {user.district or 'Unknown'}\n"
        f"Voter registered: {user.voter_registered}\n"
        f"Preferences: {json.dumps(user.preferences)}\n"
        f"Engagement: {json.dumps(user.engagement_prefs)}\n\n"
        f"## Political Context\n{political_context}\n\n"
        f"## Articles This Week\n{json.dumps(articles_json, indent=2)}"
    )

    try:
        # TODO: Switch to Batch API for multi-user in Phase 1
        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        result = json.loads(raw_text)

        items = [
            DigestItem(
                article_id=item.get("article_id", ""),
                headline=item.get("headline", ""),
                summary=item.get("summary", ""),
                why_it_matters=item.get("why_it_matters", ""),
                source_url=item.get("source_url", ""),
            )
            for item in result.get("items", [])
        ]

        return Digest(
            user_id=user.id,
            week_of=date.today(),
            items=items,
            further_reading=result.get("further_reading", []),
        )

    except Exception:
        logger.exception("Failed to generate digest for user %s", user.id)
        return Digest(user_id=user.id, week_of=date.today())
