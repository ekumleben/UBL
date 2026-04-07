"""Action drafting using Sonnet 4.5.

Drafts specific emails, public comments, or testimony for recommended actions.
The user reviews, edits, and sends these themselves.
"""

from __future__ import annotations

import logging

import anthropic

from ubl.config import SONNET_MODEL, get_settings
from ubl.models import ActionRecommendation, UserProfile
from ubl.pipeline.classify import load_prompt

logger = logging.getLogger(__name__)


def draft_action(
    recommendation: ActionRecommendation,
    user: UserProfile,
    political_context: str,
) -> str:
    """Draft a civic communication for a recommended action.

    Args:
        recommendation: The action to draft for.
        user: The user's profile.
        political_context: The SF political context document.

    Returns:
        The drafted text (email body, public comment, etc.), or empty string on failure.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    system_prompt = load_prompt("action_draft.md")

    user_message = (
        f"## Action to draft\n"
        f"Action: {recommendation.action}\n"
        f"Rationale: {recommendation.rationale}\n"
        f"Contact: {recommendation.contact_info or 'Not specified'}\n\n"
        f"## User context\n"
        f"District: {user.district or 'Unknown'}\n"
        f"Preferences: {user.preferences}\n\n"
        f"## Political context\n{political_context}"
    )

    try:
        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text.strip()

    except Exception:
        logger.exception("Failed to draft action: %s", recommendation.action)
        return ""
