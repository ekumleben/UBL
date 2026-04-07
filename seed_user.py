"""One-time script to insert the founder's user profile into Supabase.

Usage:
    python seed_user.py

Requires SUPABASE_URL, SUPABASE_KEY, and FOUNDER_EMAIL in .env.
"""

from __future__ import annotations

import sys

from supabase import create_client

from ubl.config import get_settings


def main() -> None:
    settings = get_settings()

    if not settings.founder_email:
        print("Error: FOUNDER_EMAIL not set in .env")
        sys.exit(1)

    if not settings.supabase_url or not settings.supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(settings.supabase_url, settings.supabase_key)

    # Founder's preferences based on the fault-line questions from PRD Section 6.1.
    # Update these to match your actual positions.
    user_data = {
        "email": settings.founder_email,
        "district": None,  # Set to your SF district, e.g. "D5"
        "voter_registered": True,
        "preferences": {
            "housing_density": "agree",
            "homelessness_treatment": "neutral",
            "transit_priority": "agree",
            "government_reform": "agree",
            "quality_of_life_enforcement": "neutral",
            "education_reform": "neutral",
        },
        "engagement_prefs": {
            "time_budget": "20_min",  # "5_min", "20_min", "1_hour"
            "in_person": "maybe",     # "yes", "no", "maybe"
            "financial": "no",        # "yes", "no"
        },
    }

    response = (
        client.table("users")
        .upsert(user_data, on_conflict="email")
        .execute()
    )

    user_id = response.data[0]["id"]
    print(f"Seeded user: {settings.founder_email}")
    print(f"User ID: {user_id}")
    print(f"\nAdd this to your .env:\nFOUNDER_USER_ID={user_id}")


if __name__ == "__main__":
    main()
