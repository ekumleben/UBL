"""Action drafting using Sonnet 4.5.

Drafts specific emails, public comments, or testimony for recommended actions.
Calibrated to the specific recipient using supervisor theory-of-mind profiles.
The user reviews, edits, and sends these themselves.
"""

from __future__ import annotations

import logging
import re

import anthropic

from ubl.config import PROMPTS_DIR, SONNET_MODEL, get_settings
from ubl.models import ActionRecommendation, UserProfile
from ubl.pipeline.classify import load_prompt

logger = logging.getLogger(__name__)

# Parse supervisor profiles from the markdown file into a dict
_supervisor_profiles: dict[str, str] = {}


def _load_supervisor_profiles() -> dict[str, str]:
    """Load supervisor profiles keyed by district (e.g. 'D2')."""
    global _supervisor_profiles
    if _supervisor_profiles:
        return _supervisor_profiles

    path = PROMPTS_DIR / "supervisor_profiles.md"
    if not path.exists():
        logger.warning("No supervisor profiles found at %s", path)
        return {}

    text = path.read_text(encoding="utf-8")
    current_district = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        match = re.match(r"^## (D\d+)", line)
        if match:
            if current_district and current_lines:
                _supervisor_profiles[current_district] = "\n".join(current_lines)
            current_district = match.group(1)
            current_lines = [line]
        elif current_district:
            current_lines.append(line)

    if current_district and current_lines:
        _supervisor_profiles[current_district] = "\n".join(current_lines)

    return _supervisor_profiles


def _resolve_recipient_district(rec: ActionRecommendation) -> str | None:
    """Try to figure out which supervisor this recommendation targets."""
    text = (rec.channel or "") + " " + (rec.contact_info or "") + " " + (rec.recipient or "")
    text = text.lower()

    district_map = {
        "chan": "D1", "sherrill": "D2", "sauter": "D3", "wong": "D4",
        "mahmood": "D5", "dorsey": "D6", "melgar": "D7", "mandelman": "D8",
        "fielder": "D9", "walton": "D10", "chen": "D11",
    }

    for name, district in district_map.items():
        if name in text:
            return district

    # Check for board.of.supervisors (general comment — use user's own district)
    if "board.of.supervisors" in text:
        return None  # will use user's district

    return None


def draft_action(
    recommendation: ActionRecommendation,
    user: UserProfile,
    political_context: str,
) -> str:
    """Draft a civic communication for a recommended action.

    Calibrates the draft to the specific recipient using supervisor
    theory-of-mind profiles — what they care about, what framing works,
    what kind of constituent voice lands.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    system_prompt = load_prompt("action_draft.md")
    profiles = _load_supervisor_profiles()

    # Find the right supervisor profile
    recipient_district = _resolve_recipient_district(recommendation)
    if not recipient_district:
        recipient_district = user.district

    supervisor_profile = ""
    if recipient_district and recipient_district in profiles:
        supervisor_profile = profiles[recipient_district]

    # Build user context with material position from free text
    freetext = user.preferences.get("freetext", {})
    engagement = user.engagement_prefs if hasattr(user, "engagement_prefs") else {}

    user_context_parts = [
        f"District: {user.district or 'Unknown'}",
        f"Engagement: {engagement}",
    ]
    if freetext.get("context"):
        user_context_parts.append(f"About them: {freetext['context']}")
    if freetext.get("priorities"):
        user_context_parts.append(f"Their priorities: {freetext['priorities']}")

    user_message = (
        f"## Action to draft\n"
        f"Action: {recommendation.action}\n"
        f"Action type: {recommendation.action_type}\n"
        f"Rationale: {recommendation.rationale}\n"
        f"Channel: {recommendation.channel or 'Not specified'}\n"
        f"Contact: {recommendation.contact_info or 'Not specified'}\n"
        f"Decision stage: {recommendation.decision_stage}\n"
        f"Deadline: {recommendation.deadline or 'None specified'}\n\n"
        f"## Supervisor profile\n{supervisor_profile or 'No specific profile available. Draft for a general audience.'}\n\n"
        f"## User context\n" + "\n".join(user_context_parts) + "\n\n"
        f"## Political context (abbreviated)\n"
        f"{political_context[:4000]}"  # Truncate to save tokens — the supervisor profile carries the key intel
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
