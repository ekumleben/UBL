"""Database access layer for UBL. All Supabase reads and writes go through here."""

from __future__ import annotations

import functools
import logging
from datetime import datetime

from supabase import Client, create_client

from ubl.config import get_settings
from ubl.models import ClassifiedArticle, Digest, UserProfile

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Create and cache a Supabase client."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def store_articles(articles: list[ClassifiedArticle]) -> int:
    """Upsert classified articles into the database.

    On URL conflict, updates classification fields (topics, relevance_score,
    summary, is_time_sensitive, deadline, relevance_tags).

    Returns:
        Number of articles stored.
    """
    if not articles:
        return 0

    client = get_supabase_client()
    stored = 0

    for article in articles:
        try:
            row = {
                "source": article.source,
                "title": article.title,
                "url": article.url,
                "content": article.content,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "topics": article.topics,
                "relevance_score": article.relevance_score,
                "summary": article.summary,
                "is_time_sensitive": article.is_time_sensitive,
                "deadline": article.deadline.isoformat() if article.deadline else None,
                "relevance_tags": article.relevance_tags,
            }
            client.table("articles").upsert(row, on_conflict="url").execute()
            stored += 1
        except Exception:
            logger.exception("Failed to store article: %s", article.url)

    logger.info("Stored %d/%d articles", stored, len(articles))
    return stored


def get_recent_articles(
    since: datetime,
    topics: list[str] | None = None,
) -> list[ClassifiedArticle]:
    """Fetch articles published after `since`, optionally filtered by topic.

    Args:
        since: Only return articles published after this datetime.
        topics: If provided, only return articles matching at least one topic.

    Returns:
        List of ClassifiedArticle objects sorted by published_at descending.
    """
    client = get_supabase_client()

    try:
        query = (
            client.table("articles")
            .select("*")
            .gte("published_at", since.isoformat())
            .order("published_at", desc=True)
        )

        if topics:
            # Filter articles that overlap with the requested topics.
            # Supabase/PostgREST supports the `ov` (overlap) operator for arrays.
            query = query.overlap("topics", topics)

        response = query.execute()

        return [
            ClassifiedArticle(
                source=row["source"],
                title=row["title"],
                url=row["url"],
                content=row.get("content"),
                published_at=row.get("published_at"),
                topics=row.get("topics", []),
                relevance_score=row.get("relevance_score", 0.0),
                summary=row.get("summary", ""),
                is_time_sensitive=row.get("is_time_sensitive", False),
                deadline=row.get("deadline"),
                relevance_tags=row.get("relevance_tags", {}),
            )
            for row in response.data
        ]
    except Exception:
        logger.exception("Failed to fetch recent articles since %s", since)
        return []


def get_stored_urls(urls: list[str]) -> set[str]:
    """Check which URLs are already stored in the database.

    Args:
        urls: List of article URLs to check.

    Returns:
        Set of URLs that already exist in the articles table.
    """
    if not urls:
        return set()

    client = get_supabase_client()

    try:
        response = (
            client.table("articles")
            .select("url")
            .in_("url", urls)
            .execute()
        )
        return {row["url"] for row in response.data}
    except Exception:
        logger.exception("Failed to check stored URLs")
        return set()


def get_user_profile(user_id: str) -> UserProfile | None:
    """Fetch a user profile by ID.

    Returns:
        UserProfile or None if not found.
    """
    client = get_supabase_client()

    try:
        response = (
            client.table("users")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        row = response.data
        return UserProfile(
            id=row["id"],
            email=row["email"],
            district=row.get("district"),
            voter_registered=row.get("voter_registered"),
            preferences=row.get("preferences", {}),
            engagement_prefs=row.get("engagement_prefs", {}),
        )
    except Exception:
        logger.exception("Failed to fetch user profile: %s", user_id)
        return None


def store_digest(digest: Digest) -> str | None:
    """Insert a generated digest into the database.

    Returns:
        The digest ID, or None on failure.
    """
    client = get_supabase_client()

    try:
        row = {
            "user_id": digest.user_id,
            "week_of": digest.week_of.isoformat(),
            "content": digest.model_dump(mode="json"),
        }
        response = client.table("digests").insert(row).execute()
        digest_id = response.data[0]["id"]
        logger.info("Stored digest %s for user %s", digest_id, digest.user_id)
        return digest_id
    except Exception:
        logger.exception("Failed to store digest for user %s", digest.user_id)
        return None


def mark_digest_sent(digest_id: str) -> None:
    """Update a digest's email_sent_at timestamp."""
    client = get_supabase_client()

    try:
        client.table("digests").update(
            {"email_sent_at": datetime.utcnow().isoformat()}
        ).eq("id", digest_id).execute()
        logger.info("Marked digest %s as sent", digest_id)
    except Exception:
        logger.exception("Failed to mark digest %s as sent", digest_id)
