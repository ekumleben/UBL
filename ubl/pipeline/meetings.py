"""SF.gov meetings API ingestion.

Fetches upcoming city government meetings from the SF.gov Wagtail CMS API.
These provide hearing dates, agendas, and committee schedules that RSS feeds
don't cover — critical for attaching deadlines to action recommendations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from ubl.models import RawArticle

logger = logging.getLogger(__name__)

SFGOV_API_LIST = "https://api.sf.gov/api/v2/pages/"
SFGOV_API_DETAIL = "https://api.sf.gov/api/v2/pages/{}/"


def fetch_upcoming_meetings(
    days_ahead: int = 21,
    limit: int = 100,
) -> list[RawArticle]:
    """Fetch upcoming city government meetings from SF.gov API.

    Returns meetings as RawArticle objects so they flow through the same
    classification and storage pipeline as RSS articles.
    """
    try:
        now = datetime.now(timezone.utc)

        with httpx.Client(timeout=30) as client:
            resp = client.get(SFGOV_API_LIST, params={
                "type": "sf.Meeting",
                "locale": "en",
                "limit": limit,
                "order": "-id",
                "format": "json",
            })
            resp.raise_for_status()
            page_list = resp.json().get("items", [])

            articles: list[RawArticle] = []
            seen_dates: set[str] = set()

            for page_ref in page_list:
                page_id = page_ref.get("id")
                if not page_id:
                    continue

                detail = client.get(
                    SFGOV_API_DETAIL.format(page_id),
                    params={"format": "json"},
                ).json()

                if detail.get("cancelled"):
                    continue

                date_time_blocks = detail.get("date_time", [])
                if not date_time_blocks:
                    continue

                dt_value = date_time_blocks[0].get("value", {})
                start_date = dt_value.get("start_date")
                start_time = dt_value.get("start_time", "00:00:00")
                if not start_date:
                    continue

                try:
                    meeting_dt = datetime.fromisoformat(
                        f"{start_date}T{start_time}+00:00"
                    )
                except (ValueError, TypeError):
                    continue

                if meeting_dt < now:
                    continue
                if (meeting_dt - now).days > days_ahead:
                    continue

                title = detail.get("title", "")
                dedup_key = f"{start_date}|{title}"
                if dedup_key in seen_dates:
                    continue
                seen_dates.add(dedup_key)

                agency = ""
                agencies = detail.get("primary_agencies") or detail.get("primary_agency")
                if isinstance(agencies, list) and agencies:
                    first = agencies[0]
                    if isinstance(first, dict):
                        agency = first.get("title", "")
                elif isinstance(agencies, dict):
                    agency = agencies.get("title", "")

                location = ""
                loc_data = detail.get("meeting_location")
                if isinstance(loc_data, list) and loc_data:
                    loc_val = loc_data[0].get("value", {})
                    if isinstance(loc_val, dict):
                        location = loc_val.get("address", "") or loc_val.get("text", "")
                    elif isinstance(loc_val, str):
                        location = loc_val

                agenda_text = _extract_agenda(detail.get("agenda"))

                content_parts = []
                if agency:
                    content_parts.append(f"Agency: {agency}")
                content_parts.append(
                    f"Date: {start_date} at {start_time}"
                )
                if location:
                    content_parts.append(f"Location: {location}")
                if agenda_text:
                    content_parts.append(f"\nAgenda:\n{agenda_text}")

                slug = detail.get("meta", {}).get("slug", "")
                html_url = detail.get("meta", {}).get("html_url", "")
                url = html_url or (f"https://sf.gov/{slug}" if slug else f"https://sf.gov/meetings#{page_id}")

                articles.append(
                    RawArticle(
                        source="sfgov_meetings",
                        title=f"[Meeting] {title}",
                        url=url,
                        content="\n".join(content_parts),
                        published_at=meeting_dt,
                    )
                )

        logger.info("Fetched %d upcoming meetings from SF.gov API", len(articles))
        return articles

    except Exception:
        logger.exception("Failed to fetch meetings from SF.gov API")
        return []


def _extract_agenda(agenda: list | None) -> str:
    """Extract agenda text from Wagtail StreamField blocks."""
    if not agenda or not isinstance(agenda, list):
        return ""

    parts: list[str] = []
    for block in agenda:
        if not isinstance(block, dict):
            continue
        value = block.get("value", "")
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
        elif isinstance(value, dict):
            text = value.get("text", "") or value.get("value", "")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts)
