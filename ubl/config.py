"""Centralized configuration for UBL. Loads settings from environment variables."""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from ubl.models import FeedSource

# Project root directory (ubl/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Prompt files directory
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Model IDs
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-5-20250929"


# RSS feed registry — all confirmed-working feeds from CLAUDE.md Section 1.
# Priority: critical > high > medium. full_text indicates whether the RSS feed
# provides article body text (vs. just a summary).
DEFAULT_FEEDS: list[FeedSource] = [
    # Critical — full text, free
    FeedSource(name="mission_local", url="https://missionlocal.org/feed/", priority="critical", full_text=True),
    FeedSource(name="48_hills", url="https://48hills.org/feed", priority="critical", full_text=True),
    FeedSource(name="streetsblog_sf", url="https://sf.streetsblog.org/feed", priority="critical", full_text=True),
    # High priority — summaries only
    FeedSource(name="sf_standard", url="https://sfstandard.com/feed", priority="high", full_text=False),
    FeedSource(name="sf_standard_politics", url="https://sfstandard.com/category/politics/feed", priority="high", full_text=False),
    # Medium priority
    FeedSource(name="sfist", url="https://sfist.com/rss", priority="medium", full_text=False),
    FeedSource(name="growsf", url="https://report.growsf.org/feed", priority="medium", full_text=True),
    FeedSource(name="the_frisc", url="https://thefrisc.com/feed/", priority="medium", full_text=True),
    FeedSource(name="sf_public_press", url="https://sfpublicpress.org/feed", priority="medium", full_text=True),
]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API keys
    anthropic_api_key: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    # service_role key — bypasses RLS; used by the pipeline only, never the browser
    supabase_service_key: str = ""
    resend_api_key: str = ""

    # Founder config (Phase 0)
    founder_email: str = ""
    founder_user_id: str = ""

    # Pipeline settings
    dry_run: bool = True
    log_level: str = "INFO"

    # Public site base URL (for unsubscribe/console links in emails)
    site_url: str = "https://app.universalbasiclobbyist.ai"

    # RSS feeds
    feeds: list[FeedSource] = Field(default_factory=lambda: DEFAULT_FEEDS)

    model_config = {"env_file": PROJECT_ROOT / ".env", "env_file_encoding": "utf-8"}


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
