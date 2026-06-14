"""Digest pipeline orchestrator. Generates a full digest for a user.

Usage:
    python -m ubl.digest.run
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from ubl.config import PROMPTS_DIR, get_settings
from ubl.digest.draft import draft_action
from ubl.digest.generate import generate_digest
from ubl.digest.leverage import assess_leverage
from ubl.logging_config import setup_logging
from ubl.models import Digest
from ubl.pipeline.store import get_recent_articles, get_user_profile, store_digest

logger = logging.getLogger(__name__)


def _load_political_context() -> str:
    """Load the SF political context and grammar documents.

    The grammar is the stable structural layer (how SF politics works).
    The context is the mutable layer (who's in office, what's active now).
    Both are concatenated and passed to the LLM together.
    """
    parts: list[str] = []

    grammar_file = PROMPTS_DIR / "sf_political_grammar.md"
    if grammar_file.exists():
        parts.append(grammar_file.read_text(encoding="utf-8"))
    else:
        logger.warning("No political grammar document found")

    context_file = PROMPTS_DIR / "sf_political_context.md"
    if context_file.exists():
        parts.append(context_file.read_text(encoding="utf-8"))
    else:
        example_file = PROMPTS_DIR / "sf_political_context.example.md"
        if example_file.exists():
            logger.warning(
                "Using example political context — create prompts/sf_political_context.md "
                "with real data for better results"
            )
            parts.append(example_file.read_text(encoding="utf-8"))
        else:
            logger.warning("No political context document found")

    return "\n\n---\n\n".join(parts) if parts else "No political context available."


def run_digest_pipeline(
    user_id: str,
    dry_run: bool = False,
) -> Digest:
    """Generate a complete digest for a user.

    Steps:
        1. Load user profile from database
        2. Load recent articles (last 7 days)
        3. Load political context
        4. Run leverage assessment (Sonnet + thinking)
        5. Generate digest (Sonnet)
        6. Draft actions for recommendations
        7. Store digest in database (unless dry_run)

    Args:
        user_id: The user's ID.
        dry_run: If True, skip storing to database.

    Returns:
        The complete Digest object.
    """
    start = time.time()
    logger.info("Starting digest pipeline for user %s (dry_run=%s)", user_id, dry_run)

    # 1. Load user profile
    user = get_user_profile(user_id)
    if user is None:
        logger.error("User %s not found", user_id)
        raise ValueError(f"User {user_id} not found")

    # 2. Load recent articles
    since = datetime.now(timezone.utc) - timedelta(days=7)
    articles = get_recent_articles(since)
    logger.info("Found %d articles from the past week", len(articles))

    if not articles:
        logger.warning("No articles found — digest will be empty")

    # 3. Load political context
    political_context = _load_political_context()

    # 4. Leverage assessment
    logger.info("Running leverage assessment")
    leverage = assess_leverage(user, articles, political_context)
    logger.info(
        "Leverage assessment: %d recommendations, quiet_week=%s",
        len(leverage.recommendations),
        leverage.is_quiet_week,
    )

    # 5. Generate digest
    logger.info("Generating digest")
    digest = generate_digest(user, articles, political_context)
    digest.leverage = leverage
    digest._district = user.district  # for email template supervisor lookup

    # 6. Draft actions for recommendations that need them
    for rec in leverage.recommendations:
        if not rec.draft_text and (rec.contact_info or rec.channel):
            logger.info("Drafting action: %s", rec.action[:60])
            rec.draft_text = draft_action(rec, user, political_context)

    # 7. Store (always store, even on dry run — console needs the data)
    digest_id = store_digest(digest)
    if digest_id:
        digest.id = digest_id
        logger.info("Digest stored with ID %s", digest_id)

    elapsed = time.time() - start
    logger.info(
        "Digest pipeline complete in %.1fs: %d items, %d recommendations",
        elapsed,
        len(digest.items),
        len(digest.leverage.recommendations),
    )
    return digest


if __name__ == "__main__":
    setup_logging()
    settings = get_settings()
    if not settings.founder_user_id:
        print("Error: FOUNDER_USER_ID not set in .env")
    else:
        digest = run_digest_pipeline(settings.founder_user_id, dry_run=settings.dry_run)
        print(f"\nDigest: {len(digest.items)} items, {len(digest.leverage.recommendations)} recommendations")
