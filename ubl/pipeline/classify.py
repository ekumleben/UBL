"""Article classification using Haiku 4.5.

Classifies each article by topic, civic relevance, and time-sensitivity.
Uses the prompt in prompts/classify_article.md.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import anthropic

from ubl.config import HAIKU_MODEL, PROMPTS_DIR, get_settings
from ubl.models import ClassifiedArticle, RawArticle

logger = logging.getLogger(__name__)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt file from the prompts directory.

    Args:
        prompt_name: Filename in the prompts directory (e.g. "classify_article.md").

    Returns:
        The prompt text.
    """
    path = PROMPTS_DIR / prompt_name
    return path.read_text(encoding="utf-8")


def _build_user_message(article: RawArticle) -> str:
    """Build the user message for article classification."""
    parts = [f"Title: {article.title}", f"Source: {article.source}"]
    if article.content:
        # Truncate very long content to keep costs down
        content = article.content[:3000]
        parts.append(f"Content:\n{content}")
    if article.published_at:
        parts.append(f"Published: {article.published_at.isoformat()}")
    return "\n\n".join(parts)


def classify_article(
    article: RawArticle,
    client: anthropic.Anthropic | None = None,
) -> ClassifiedArticle:
    """Classify a single article using Haiku 4.5.

    On API failure, returns the article with default classification values
    (topics=["unclassified"], relevance_score=0.5) rather than crashing.

    Args:
        article: The raw article to classify.
        client: Optional pre-created Anthropic client (for reuse across calls).

    Returns:
        A ClassifiedArticle with classification fields populated.
    """
    if client is None:
        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    system_prompt = load_prompt("classify_article.md")
    user_message = _build_user_message(article)

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()

        # Handle potential markdown code fences in response
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        result = json.loads(raw_text)

        return ClassifiedArticle(
            source=article.source,
            title=article.title,
            url=article.url,
            content=article.content,
            published_at=article.published_at,
            topics=result.get("topics", ["unclassified"]),
            relevance_score=result.get("relevance_score", 0.5),
            summary=result.get("summary", ""),
            is_time_sensitive=result.get("is_time_sensitive", False),
            deadline=result.get("deadline"),
            relevance_tags=result,
        )

    except Exception:
        logger.exception("Failed to classify article: %s", article.url)
        return ClassifiedArticle(
            source=article.source,
            title=article.title,
            url=article.url,
            content=article.content,
            published_at=article.published_at,
            topics=["unclassified"],
            relevance_score=0.5,
            summary="",
        )


def classify_articles(
    articles: list[RawArticle],
    delay: float = 0.05,
) -> list[ClassifiedArticle]:
    """Classify a batch of articles.

    Args:
        articles: List of raw articles to classify.
        delay: Seconds to wait between API calls to avoid rate limits.

    Returns:
        List of ClassifiedArticle objects.
    """
    if not articles:
        return []

    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    classified: list[ClassifiedArticle] = []

    for i, article in enumerate(articles, 1):
        result = classify_article(article, client=client)
        classified.append(result)

        if i % 10 == 0:
            logger.info("Classified %d/%d articles", i, len(articles))

        if delay > 0 and i < len(articles):
            time.sleep(delay)

    logger.info(
        "Classification complete: %d articles, %d successful",
        len(articles),
        sum(1 for a in classified if a.topics != ["unclassified"]),
    )
    return classified
