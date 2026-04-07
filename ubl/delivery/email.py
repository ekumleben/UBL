"""Email delivery for UBL digests. Renders HTML and sends via Resend.

In dry-run mode, writes the rendered email to a local file for inspection.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from ubl.config import get_settings
from ubl.models import Digest
from ubl.pipeline.store import mark_digest_sent

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def _get_template_env() -> Environment:
    """Create a Jinja2 environment for email templates."""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )


def render_digest_email(digest: Digest) -> tuple[str, str]:
    """Render a digest as an HTML email.

    Args:
        digest: The digest to render.

    Returns:
        Tuple of (subject_line, html_body).
    """
    env = _get_template_env()
    template = env.get_template("digest.html")

    html = template.render(
        week_of=digest.week_of.strftime("%B %d, %Y"),
        items=digest.items,
        recommendations=digest.leverage.recommendations,
        is_quiet_week=digest.leverage.is_quiet_week,
        reasoning_summary=digest.leverage.reasoning_summary,
        further_reading=digest.further_reading,
    )

    subject = f"Your UBL Weekly — {digest.week_of.strftime('%B %d')}"
    return subject, html


def send_digest_email(
    digest: Digest,
    to_email: str,
    dry_run: bool = False,
    digest_id: str | None = None,
) -> bool:
    """Send a digest email via Resend, or save locally in dry-run mode.

    Args:
        digest: The digest to send.
        to_email: Recipient email address.
        dry_run: If True, write HTML to local file instead of sending.
        digest_id: Database ID of the digest (for marking as sent).

    Returns:
        True if sent (or saved) successfully.
    """
    subject, html = render_digest_email(digest)

    if dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"digest_{digest.week_of.isoformat()}.html"
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dry run: email saved to %s", output_path)
        return True

    settings = get_settings()

    try:
        resend.api_key = settings.resend_api_key

        result = resend.Emails.send({
            "from": "UBL <digest@universalbasiclobbyist.ai>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        })

        logger.info("Email sent to %s (id: %s)", to_email, result.get("id"))

        if digest_id:
            mark_digest_sent(digest_id)

        return True

    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False
