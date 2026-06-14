"""Granicus meeting transcript scraping and summarization.

Fetches verbatim transcripts from SF Board of Supervisors and committee
meetings via Granicus, then runs a Haiku summarization pass to extract
structured signals: supervisor positions, vote outcomes, key quotes,
and emerging issues.

The raw transcripts are auto-generated captions — readable but noisy
(mangled names, no punctuation). The Haiku pass cleans and condenses.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import anthropic
import feedparser
import httpx
from bs4 import BeautifulSoup

from ubl.config import HAIKU_MODEL, get_settings
from ubl.models import RawArticle

logger = logging.getLogger(__name__)

# Granicus view_ids for SF bodies
# Verified Granicus view_ids for SF — all confirmed to have current 2026 data
# with full transcripts available.
GRANICUS_FEEDS = {
    "bos": {
        "name": "Board of Supervisors",
        "view_id": 10,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=10",
    },
    "budget": {
        "name": "Budget and Finance Committee",
        "view_id": 7,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=7",
    },
    "gov_audit": {
        "name": "Government Audit and Oversight Committee",
        "view_id": 11,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=11",
    },
    "rules": {
        "name": "Rules Committee",
        "view_id": 13,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=13",
    },
    "planning": {
        "name": "Planning Commission",
        "view_id": 20,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=20",
    },
    "police": {
        "name": "Police Commission",
        "view_id": 21,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=21",
    },
    "transportation": {
        "name": "Transportation Authority",
        "view_id": 24,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=24",
    },
    "board_of_appeals": {
        "name": "Board of Appeals",
        "view_id": 6,
        "rss": "https://sanfrancisco.granicus.com/ViewPublisherRSS.php?view_id=6",
    },
}

# Common caption-to-real-name fixes for SF supervisors
NAME_FIXES = {
    "mandolin": "Mandelman",
    "mandelman": "Mandelman",
    "sadr": "Sauter",
    "sauter": "Sauter",
    "cheryl": "Sherrill",
    "sherrell": "Sherrill",
    "sherrill": "Sherrill",
    "wang huang": "Wong",
    "wong": "Wong",
    "chin": "Chan",  # context-dependent; Haiku resolves
    "mahmud": "Mahmood",
    "mahmood": "Mahmood",
    "melgar": "Melgar",
    "walton": "Walton",
    "dorsey": "Dorsey",
    "fielder": "Fielder",
    "chen": "Chen",
    "chan": "Chan",
}

TRANSCRIPT_URL = "https://sanfrancisco.granicus.com/TranscriptViewer.php"

SUMMARIZE_PROMPT = """You are summarizing a San Francisco Board of Supervisors (or committee) meeting transcript for a civic engagement tool.

The transcript is auto-generated captions — names are often mangled. Correct names:
D1 Connie Chan ("Chin"), D2 Stephen Sherrill ("Cheryl"/"Sherrell"), D3 Danny Sauter ("Sadr"), D4 Alan Wong ("Wang Huang"), D5 Bilal Mahmood ("Mahmud"), D6 Matt Dorsey, D7 Myrna Melgar, D8 Rafael Mandelman/Board President ("Mandolin"), D9 Jackie Fielder (on leave), D10 Shamann Walton, D11 Chyanne Chen ("Chin" — context), Mayor Daniel Lurie.

Write a structured plain-text summary using EXACTLY this format. Use --- to separate sections. Do NOT use JSON. Do NOT use quotation marks around text.

MEETING: [type]
DATE: [YYYY-MM-DD]
ATTENDANCE: [comma-separated names of supervisors present]

---ITEMS---
Each item on its own line:
ITEM: [topic] | ACTION: [passed/failed/continued/etc] | VOTE: [e.g. 9-0] | SPEAKERS: [Name: position, Name: position]

---POSITIONS---
Each supervisor on its own line:
[Name]: [summary of positions taken]

---QUOTES---
Each on its own line:
[Speaker] - [paraphrased quote, no quotation marks]

---EMERGING---
Each on its own line, describing upcoming fights or windows

Focus on what was DECIDED, who took what POSITION, and what signals FUTURE action windows. Skip procedural minutiae. Under 1200 words."""


def fetch_transcript(view_id: int, clip_id: int) -> str | None:
    """Fetch and clean a Granicus transcript."""
    try:
        url = f"{TRANSCRIPT_URL}?view_id={view_id}&clip_id={clip_id}"
        r = httpx.get(url, timeout=30, follow_redirects=True)
        if r.status_code != 200:
            logger.warning("Transcript %d returned %d", clip_id, r.status_code)
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        for br in soup.find_all("br"):
            br.replace_with("\n")

        text = soup.get_text()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        if len(lines) < 20:
            logger.warning("Transcript %d too short (%d lines)", clip_id, len(lines))
            return None

        # Basic name cleanup in the raw text
        full_text = "\n".join(lines)
        return full_text

    except Exception:
        logger.exception("Failed to fetch transcript clip_id=%d", clip_id)
        return None


def summarize_transcript(transcript: str, meeting_title: str) -> dict | None:
    """Run a Haiku summarization pass over a raw transcript."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Truncate if extremely long (Haiku context is 200K but let's be reasonable)
    max_chars = 80000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[TRANSCRIPT TRUNCATED]"

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=2048,
            system=SUMMARIZE_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Meeting: {meeting_title}\n\nTranscript:\n{transcript}",
                }
            ],
        )

        raw = response.content[0].text.strip()

        # Parse the structured plain-text format
        result = {
            "meeting_type": "",
            "date": "",
            "key_items": [],
            "supervisor_positions": {},
            "notable_quotes": [],
            "emerging_issues": [],
            "attendance": [],
        }

        current_section = "header"
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("---ITEMS"):
                current_section = "items"
                continue
            elif line.startswith("---POSITIONS"):
                current_section = "positions"
                continue
            elif line.startswith("---QUOTES"):
                current_section = "quotes"
                continue
            elif line.startswith("---EMERGING"):
                current_section = "emerging"
                continue
            elif line.startswith("---"):
                continue

            if current_section == "header":
                if line.startswith("MEETING:"):
                    result["meeting_type"] = line.split(":", 1)[1].strip()
                elif line.startswith("DATE:"):
                    result["date"] = line.split(":", 1)[1].strip()
                elif line.startswith("ATTENDANCE:"):
                    names = line.split(":", 1)[1].strip()
                    result["attendance"] = [n.strip() for n in names.split(",") if n.strip()]

            elif current_section == "items":
                if line.startswith("ITEM:"):
                    parts = line.split("|")
                    item = {"topic": parts[0].replace("ITEM:", "").strip()}
                    for part in parts[1:]:
                        part = part.strip()
                        if part.startswith("ACTION:"):
                            item["action_taken"] = part.replace("ACTION:", "").strip()
                        elif part.startswith("VOTE:"):
                            item["vote"] = part.replace("VOTE:", "").strip()
                        elif part.startswith("SPEAKERS:"):
                            item["key_speakers"] = [s.strip() for s in part.replace("SPEAKERS:", "").split(",") if s.strip()]
                    result["key_items"].append(item)

            elif current_section == "positions":
                if ":" in line:
                    name, pos = line.split(":", 1)
                    result["supervisor_positions"][name.strip()] = pos.strip()

            elif current_section == "quotes":
                if " - " in line:
                    result["notable_quotes"].append(line)
                elif line:
                    result["notable_quotes"].append(line)

            elif current_section == "emerging":
                if line:
                    result["emerging_issues"].append(line)

        return result

    except Exception:
        logger.exception("Failed to summarize transcript: %s", meeting_title)
        return None


def fetch_recent_transcripts(
    bodies: list[str] | None = None,
    max_per_body: int = 2,
) -> list[RawArticle]:
    """Fetch and summarize recent meeting transcripts.

    Skips transcripts already stored in the database (by URL/clip_id).
    Returns summarized transcripts as RawArticle objects so they flow
    through the same storage pipeline.
    """
    if bodies is None:
        bodies = list(GRANICUS_FEEDS.keys())

    # Get already-stored transcript URLs to skip re-processing
    from ubl.pipeline.store import get_stored_urls

    all_candidate_urls: list[str] = []
    feed_entries_by_body: dict[str, list] = {}

    for body_key in bodies:
        feed_info = GRANICUS_FEEDS.get(body_key)
        if not feed_info:
            continue
        feed = feedparser.parse(feed_info["rss"])
        entries = []
        for entry in feed.entries:
            link = entry.get("link", "")
            clip_match = re.search(r"clip_id=(\d+)", link)
            if clip_match:
                url = f"https://sanfrancisco.granicus.com/MediaPlayer.php?view_id={feed_info['view_id']}&clip_id={clip_match.group(1)}"
                all_candidate_urls.append(url)
                entries.append((entry, int(clip_match.group(1)), url))
        feed_entries_by_body[body_key] = entries

    already_stored = get_stored_urls(all_candidate_urls) if all_candidate_urls else set()

    articles: list[RawArticle] = []

    for body_key in bodies:
        feed_info = GRANICUS_FEEDS.get(body_key)
        if not feed_info:
            continue

        logger.info("Fetching transcripts for %s", feed_info["name"])
        entries = feed_entries_by_body.get(body_key, [])

        count = 0
        for entry, clip_id, url in entries:
            if count >= max_per_body:
                break

            if url in already_stored:
                logger.debug("Skipping already-stored transcript clip_id=%d", clip_id)
                continue

            title = entry.get("title", "")

            # Fetch the raw transcript
            transcript = fetch_transcript(feed_info["view_id"], clip_id)
            if not transcript:
                continue

            word_count = len(transcript.split())
            logger.info(
                "Transcript %s: %d words, summarizing...", title, word_count
            )

            # Summarize with Haiku
            summary = summarize_transcript(transcript, title)
            if not summary:
                continue

            # Build content from the structured summary
            content_parts = [
                f"Meeting: {title}",
                f"Body: {feed_info['name']}",
            ]

            if summary.get("attendance"):
                content_parts.append(
                    f"Present: {', '.join(summary['attendance'])}"
                )

            if summary.get("key_items"):
                content_parts.append("\nKey items:")
                for item in summary["key_items"]:
                    line = f"- {item.get('topic', '?')}"
                    if item.get("action_taken"):
                        line += f" — {item['action_taken']}"
                    if item.get("vote"):
                        line += f" ({item['vote']})"
                    content_parts.append(line)
                    for speaker in item.get("key_speakers", []):
                        content_parts.append(f"  {speaker}")

            if summary.get("supervisor_positions"):
                content_parts.append("\nSupervisor positions:")
                for name, pos in summary["supervisor_positions"].items():
                    if pos:
                        content_parts.append(f"- {name}: {pos}")

            if summary.get("notable_quotes"):
                content_parts.append("\nNotable quotes:")
                for q in summary["notable_quotes"]:
                    content_parts.append(f'- "{q}"')

            if summary.get("emerging_issues"):
                content_parts.append("\nEmerging issues:")
                for issue in summary["emerging_issues"]:
                    content_parts.append(f"- {issue}")

            if summary.get("_raw_summary"):
                content_parts.append(f"\nRaw summary:\n{summary['_raw_summary']}")

            # Parse date from feed entry
            pub_date = None
            raw_date = entry.get("published")
            if raw_date:
                try:
                    from email.utils import parsedate_to_datetime

                    pub_date = parsedate_to_datetime(raw_date)
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            articles.append(
                RawArticle(
                    source=f"granicus_{body_key}",
                    title=f"[Transcript] {title}",
                    url=url,
                    content="\n".join(content_parts),
                    published_at=pub_date,
                )
            )

            count += 1
            logger.info("Summarized: %s (%d key items)", title, len(summary.get("key_items", [])))

    logger.info("Fetched and summarized %d transcripts", len(articles))
    return articles
