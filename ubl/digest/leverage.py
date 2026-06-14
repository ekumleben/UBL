"""Leverage assessment using Sonnet 4.5 with extended thinking.

This is the "lobbyist brain" — it reasons about political dynamics, timing,
and the user's specific position to identify the highest-leverage civic actions.
"""

from __future__ import annotations

import json
import logging

import anthropic

from ubl.config import SONNET_MODEL, get_settings
from ubl.models import (
    ActionRecommendation,
    ClassifiedArticle,
    LeverageAssessment,
    UserProfile,
)
from ubl.pipeline.classify import load_prompt

logger = logging.getLogger(__name__)


def assess_leverage(
    user: UserProfile,
    articles: list[ClassifiedArticle],
    political_context: str,
) -> LeverageAssessment:
    """Assess the highest-leverage civic actions for the user this week.

    Uses Sonnet 4.5 with extended thinking to reason through political dynamics
    before producing recommendations. Budget: 3-4K thinking tokens.

    Args:
        user: The user's profile.
        articles: Classified articles from the past week (already filtered for relevance).
        political_context: The SF political context document text.

    Returns:
        A LeverageAssessment with ranked recommendations.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    system_prompt = load_prompt("leverage_assessment.md")

    # Focus on time-sensitive and high-relevance articles
    high_priority = [
        a for a in articles
        if a.relevance_score >= 0.5 or a.is_time_sensitive
    ]

    if not high_priority:
        logger.info("No high-priority articles for leverage assessment")
        return LeverageAssessment(
            is_quiet_week=True,
            reasoning_summary="No high-priority civic engagement opportunities identified this week.",
        )

    articles_json = [
        {
            "title": a.title,
            "source": a.source,
            "summary": a.summary,
            "topics": a.topics,
            "relevance_score": a.relevance_score,
            "is_time_sensitive": a.is_time_sensitive,
            "deadline": a.deadline.isoformat() if a.deadline else None,
            "url": a.url,
        }
        for a in high_priority[:15]
    ]

    freetext = user.preferences.get("freetext", {})
    freetext_block = ""
    if freetext:
        parts = []
        if freetext.get("priorities"):
            parts.append(f"What matters to them: {freetext['priorities']}")
        if freetext.get("tracking"):
            parts.append(f"Tracking: {freetext['tracking']}")
        if freetext.get("context"):
            parts.append(f"About them: {freetext['context']}")
        freetext_block = "\n".join(parts) + "\n"

    user_message = (
        f"## User Profile\n"
        f"District: {user.district or 'Unknown'}\n"
        f"Voter registered: {user.voter_registered}\n"
        f"{freetext_block}"
        f"Preferences: {json.dumps(user.preferences)}\n"
        f"Engagement: {json.dumps(user.engagement_prefs)}\n\n"
        f"## Political Context\n{political_context}\n\n"
        f"## This Week's Articles\n{json.dumps(articles_json, indent=2)}"
    )

    try:
        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 4000,
            },
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract text from response (thinking blocks come first, then text)
        raw_text = ""
        for block in response.content:
            if block.type == "text":
                raw_text = block.text.strip()
                break

        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        result = json.loads(raw_text)

        recommendations = [
            ActionRecommendation(
                action=rec.get("action", ""),
                rationale=rec.get("rationale", ""),
                effort_estimate=rec.get("effort_estimate", ""),
                alternatives=rec.get("alternatives", []),
                draft_text=rec.get("draft_text"),
                contact_info=rec.get("contact_info"),
                action_type=rec.get("action_type", "email"),
                channel=rec.get("channel", ""),
                recipient=rec.get("recipient", ""),
                deadline=rec.get("deadline"),
                decision_stage=rec.get("decision_stage", ""),
                legal_weight=rec.get("legal_weight", "none"),
                scope_advice=rec.get("scope_advice", ""),
            )
            for rec in result.get("recommendations", [])
        ]

        return LeverageAssessment(
            recommendations=recommendations,
            is_quiet_week=result.get("is_quiet_week", False),
            reasoning_summary=result.get("reasoning_summary", ""),
        )

    except Exception:
        logger.exception("Failed to assess leverage for user %s", user.id)
        return LeverageAssessment(
            is_quiet_week=True,
            reasoning_summary="Unable to complete leverage assessment this week.",
        )
