"""Pydantic models shared across all UBL modules.

This is the single source of truth for data shapes. Every module imports from
here. No raw dicts with undocumented keys should cross module boundaries.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Data source models
# ---------------------------------------------------------------------------

class FeedSource(BaseModel):
    """An RSS feed source configured for ingestion."""

    name: str
    url: str
    priority: str  # "critical", "high", "medium"
    full_text: bool


# ---------------------------------------------------------------------------
# Article models
# ---------------------------------------------------------------------------

class RawArticle(BaseModel):
    """An article as fetched from an RSS feed, before classification."""

    source: str
    title: str
    url: str
    content: str | None = None
    published_at: datetime | None = None


class ClassifiedArticle(BaseModel):
    """An article after Haiku 4.5 classification."""

    model_config = ConfigDict(from_attributes=True)

    source: str
    title: str
    url: str
    content: str | None = None
    published_at: datetime | None = None
    topics: list[str] = []
    relevance_score: float = 0.0
    summary: str = ""
    is_time_sensitive: bool = False
    deadline: datetime | None = None
    relevance_tags: dict = {}


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    """A user's profile and preferences, loaded from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    district: str | None = None
    voter_registered: bool | None = None
    preferences: dict = {}
    engagement_prefs: dict = {}


# ---------------------------------------------------------------------------
# Digest models
# ---------------------------------------------------------------------------

class DigestItem(BaseModel):
    """A single item in the weekly digest, oriented around intervention windows."""

    article_id: str
    headline: str
    summary: str
    why_it_matters: str
    source_url: str
    decision_stage: str = "none"  # committee | full_board | commission | agency | ballot | implementation | none
    has_action_window: bool = False


class ActionRecommendation(BaseModel):
    """A recommended civic action with rationale and supporting details."""

    action: str
    rationale: str
    effort_estimate: str
    alternatives: list[str] = []
    draft_text: str | None = None
    contact_info: str | None = None
    # Intervention-routing fields
    action_type: str = "email"  # email | public_comment | hearing | vote | track | ceqa_comment | appeal
    channel: str = ""  # specific inbox, portal, or process
    recipient: str = ""  # who receives this input
    deadline: str | None = None  # when the window closes
    decision_stage: str = ""  # committee | full_board | commission | agency | ballot | implementation
    legal_weight: str = "none"  # none | procedural_record | legally_binding | preserves_standing
    scope_advice: str = ""  # widen | narrow | neutral — and why


class LeverageAssessment(BaseModel):
    """The leverage assessment output from Sonnet 4.5 + extended thinking."""

    recommendations: list[ActionRecommendation] = []
    is_quiet_week: bool = False
    reasoning_summary: str = ""


class Digest(BaseModel):
    """The complete weekly digest for a user."""

    id: str | None = None  # database ID, set after storage
    user_id: str
    week_of: date
    items: list[DigestItem] = []
    leverage: LeverageAssessment = LeverageAssessment()
    further_reading: list[dict] = []
