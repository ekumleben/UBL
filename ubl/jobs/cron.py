"""Weekly digest pipeline entry point. Runs the full pipeline end-to-end.

Usage:
    python -m ubl.jobs.cron              # Uses DRY_RUN from .env
    python -m ubl.jobs.cron --dry-run    # Force dry run
    python -m ubl.jobs.cron --send       # Force real send
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from ubl.config import get_settings
from ubl.delivery.email import send_digest_email
from ubl.digest.run import run_digest_pipeline
from ubl.logging_config import setup_logging
from ubl.pipeline.run import run_ingestion_pipeline
from ubl.pipeline.store import store_digest

logger = logging.getLogger(__name__)


def run_weekly_pipeline(dry_run: bool | None = None) -> None:
    """Run the complete weekly pipeline: ingest → digest → email.

    Args:
        dry_run: Override for dry-run mode. If None, reads from DRY_RUN env var.
    """
    settings = get_settings()
    if dry_run is None:
        dry_run = settings.dry_run

    start = time.time()
    logger.info("=" * 60)
    logger.info("UBL Weekly Pipeline — dry_run=%s", dry_run)
    logger.info("=" * 60)

    # 1. Ingest articles
    logger.info("--- Step 1: Ingestion ---")
    new_articles = run_ingestion_pipeline()
    logger.info("Ingestion complete: %d new articles", new_articles)

    # 2. Generate digest
    logger.info("--- Step 2: Digest Generation ---")
    user_id = settings.founder_user_id
    if not user_id:
        logger.error("FOUNDER_USER_ID not set in .env — cannot generate digest")
        sys.exit(1)

    digest = run_digest_pipeline(user_id, dry_run=dry_run)

    # 3. Send email
    logger.info("--- Step 3: Email Delivery ---")
    to_email = settings.founder_email
    if not to_email:
        logger.error("FOUNDER_EMAIL not set in .env — cannot send email")
        sys.exit(1)

    sent = send_digest_email(digest, to_email, dry_run=dry_run)
    if sent:
        logger.info("Email %s to %s", "saved locally" if dry_run else "sent", to_email)
    else:
        logger.error("Email delivery failed")

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(
        "Pipeline complete in %.1fs — %d items, %d recommendations",
        elapsed,
        len(digest.items),
        len(digest.leverage.recommendations),
    )
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UBL weekly pipeline")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending email (saves HTML locally)",
    )
    group.add_argument(
        "--send",
        action="store_true",
        help="Force real email send (overrides DRY_RUN env var)",
    )
    args = parser.parse_args()

    setup_logging(get_settings().log_level)

    dry_run = None
    if args.dry_run:
        dry_run = True
    elif args.send:
        dry_run = False

    try:
        run_weekly_pipeline(dry_run=dry_run)
    except Exception:
        logger.exception("Pipeline failed with unhandled exception")
        sys.exit(1)


if __name__ == "__main__":
    main()
