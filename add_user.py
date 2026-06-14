"""Add a new UBL user with district and preference profile.

Usage:
    python add_user.py                          # interactive mode
    python add_user.py --email j@example.com --district D5
    python add_user.py --email j@example.com --district D7 --quick
"""

from __future__ import annotations

import argparse
import sys

from supabase import create_client

from ubl.config import get_settings

DISTRICTS = [f"D{i}" for i in range(1, 12)]

FAULT_LINE_QUESTIONS = [
    ("density_my_block", "I'd support a 6-story apartment building on my block if it included affordable units"),
    ("encampment_sweeps", "The city should clear encampments from sidewalks even when there aren't enough shelter beds"),
    ("police_vs_social", "I'd rather have more police officers on my street than more social workers"),
    ("new_condos_help", "New market-rate condos help my neighborhood more than they hurt it"),
    ("worker_paycuts", "City workers should take pay cuts before the city cuts services"),
    ("state_override_housing", "Sacramento should be able to override SF's decisions to force more housing"),
]


def ask_preferences() -> dict:
    """Interactive preference questionnaire."""
    print("\n--- Policy Preferences ---")
    print("For each statement, enter: agree / disagree / neutral / skip\n")

    prefs = {}
    for key, statement in FAULT_LINE_QUESTIONS:
        while True:
            answer = input(f'  "{statement}"\n  → ').strip().lower()
            if answer in ("agree", "disagree", "neutral", "skip", "a", "d", "n", "s"):
                if answer == "a":
                    answer = "agree"
                elif answer == "d":
                    answer = "disagree"
                elif answer in ("n", "s", "skip"):
                    answer = "neutral"
                prefs[key] = answer
                break
            print("  (enter agree/disagree/neutral/skip)")
    return prefs


def ask_engagement() -> dict:
    """Interactive engagement preferences."""
    print("\n--- Engagement Preferences ---\n")

    time_budget = input("  Time per week? (5min / 30min / 1hour) [30min]: ").strip().lower()
    if time_budget in ("5", "5min", "5_min"):
        time_budget = "5_min"
    elif time_budget in ("1", "1hour", "1_hour", "hour"):
        time_budget = "1_hour"
    else:
        time_budget = "30_min"

    real_name = input("  Use your real name in emails/comments? (yes / officials_only / no) [officials_only]: ").strip().lower()
    if real_name not in ("yes", "officials_only", "no"):
        real_name = "officials_only"

    in_person = input("  Show up in person at hearings? (yes / maybe / no) [maybe]: ").strip().lower()
    if in_person not in ("yes", "no", "maybe"):
        in_person = "maybe"

    speak = input("  Willing to speak at a hearing? (yes / written_only / no) [written_only]: ").strip().lower()
    if speak not in ("yes", "written_only", "no"):
        speak = "written_only"

    financial = input("  Willing to donate? (yes / small / no) [no]: ").strip().lower()
    if financial not in ("yes", "small", "no"):
        financial = "no"

    return {
        "time_budget": time_budget,
        "real_name": real_name,
        "in_person": in_person,
        "speak": speak,
        "financial": financial,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a UBL user")
    parser.add_argument("--email", required=False, help="User email address")
    parser.add_argument("--district", required=False, help="SF district (D1-D11)")
    parser.add_argument("--quick", action="store_true", help="Skip preference questions (use neutral defaults)")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    email = args.email
    if not email:
        email = input("Email address: ").strip()
    if not email or "@" not in email:
        print("Error: valid email required")
        sys.exit(1)

    district = args.district
    if not district:
        print(f"\nSF Districts: {', '.join(DISTRICTS)}")
        district = input("District (e.g. D5): ").strip().upper()
    if district and district not in DISTRICTS:
        print(f"Warning: '{district}' is not a standard SF district. Proceeding anyway.")

    if args.quick:
        preferences = {key: "neutral" for key, _ in FAULT_LINE_QUESTIONS}
        engagement = {"time_budget": "30_min", "real_name": "officials_only", "in_person": "maybe", "speak": "written_only", "financial": "no"}
    else:
        preferences = ask_preferences()
        engagement = ask_engagement()

    voter = input("\nRegistered to vote in SF? (yes / no / unsure) [yes]: ").strip().lower() if not args.quick else "yes"
    voter_registered = voter != "no"

    user_data = {
        "email": email,
        "district": district or None,
        "voter_registered": voter_registered,
        "preferences": preferences,
        "engagement_prefs": engagement,
    }

    print(f"\n--- Creating user ---")
    print(f"  Email: {email}")
    print(f"  District: {district or 'not set'}")
    print(f"  Preferences: {preferences}")
    print(f"  Engagement: {engagement}")

    client = create_client(settings.supabase_url, settings.supabase_key)
    response = (
        client.table("users")
        .upsert(user_data, on_conflict="email")
        .execute()
    )

    user_id = response.data[0]["id"]
    print(f"\n✓ User created: {email}")
    print(f"  User ID: {user_id}")
    print(f"  District: {district}")
    print(f"\nThis user will receive digests on the next pipeline run.")


if __name__ == "__main__":
    main()
