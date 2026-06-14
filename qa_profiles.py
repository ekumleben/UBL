"""QA: generate digests for synthetic users with opposed profiles and compare.

Usage:
    python qa_profiles.py           # create users, generate digests, report
    python qa_profiles.py --clean   # remove QA users and their data
"""

from __future__ import annotations

import json
import sys

from supabase import create_client

from ubl.config import get_settings
from ubl.digest.run import run_digest_pipeline
from ubl.logging_config import setup_logging

QA_USERS = [
    {
        "email": "qa-d10-renter@test.ubl",
        "district": "D10",
        "voter_registered": True,
        "preferences": {
            "density_my_block": "agree",
            "encampment_sweeps": "disagree",
            "police_vs_social": "disagree",
            "new_condos_help": "disagree",
            "worker_paycuts": "disagree",
            "state_override_housing": "neutral",
            "freetext": {
                "priorities": "Rent keeps going up and friends keep getting priced out of Bayview. I care about tenant protections, displacement, and keeping working-class families in the city.",
                "tracking": "Anything about rent control expansion, Ellis Act evictions, and the budget cuts to community clinics.",
                "context": "Renter in Bayview-Hunters Point, 8 years. Work a service job downtown, take the T Third every day.",
            },
        },
        "engagement_prefs": {"time_budget": "20_min", "in_person": "maybe", "financial": "no"},
    },
    {
        "email": "qa-d2-merchant@test.ubl",
        "district": "D2",
        "voter_registered": True,
        "preferences": {
            "density_my_block": "neutral",
            "encampment_sweeps": "agree",
            "police_vs_social": "agree",
            "new_condos_help": "agree",
            "worker_paycuts": "agree",
            "state_override_housing": "neutral",
            "freetext": {
                "priorities": "I own a café on Chestnut Street. Street conditions, foot traffic, business taxes, and permits are what keep me up at night.",
                "tracking": "Small business tax changes, vacancy on commercial corridors, anything affecting Marina merchants.",
                "context": "Small business owner in the Marina, 12 years. Homeowner. Member of the merchants association.",
            },
        },
        "engagement_prefs": {"time_budget": "1_hour", "in_person": "yes", "financial": "yes"},
    },
    {
        "email": "qa-d7-parent@test.ubl",
        "district": "D7",
        "voter_registered": True,
        "preferences": {
            "density_my_block": "agree",
            "encampment_sweeps": "neutral",
            "police_vs_social": "neutral",
            "new_condos_help": "agree",
            "worker_paycuts": "disagree",
            "state_override_housing": "agree",
            "freetext": {
                "priorities": "I have two kids at SFUSD schools and bike them to school every day. School quality, safe streets, and Muni reliability are everything for us.",
                "tracking": "School closures and enrollment changes, bike lane projects on the west side, Muni service cuts.",
                "context": "Parent of two in Inner Sunset, bike commuter, married to a city employee.",
            },
        },
        "engagement_prefs": {"time_budget": "20_min", "in_person": "no", "financial": "no"},
    },
]


def get_client():
    s = get_settings()
    key = s.supabase_service_key or s.supabase_key
    return create_client(s.supabase_url, key)


def clean():
    client = get_client()
    for u in QA_USERS:
        rows = client.table("users").select("id").eq("email", u["email"]).execute()
        for row in rows.data:
            client.table("digests").delete().eq("user_id", row["id"]).execute()
            try:
                client.table("actions").delete().eq("user_id", row["id"]).execute()
            except Exception:
                pass  # actions table may not exist yet (pre-migration)
            client.table("users").delete().eq("id", row["id"]).execute()
    print("QA users and their data removed.")


def main():
    setup_logging()
    client = get_client()

    results = []
    for profile in QA_USERS:
        resp = client.table("users").upsert(profile, on_conflict="email").execute()
        user_id = resp.data[0]["id"]
        print(f"\n=== {profile['email']} ({profile['district']}) ===")
        digest = run_digest_pipeline(user_id, dry_run=True)
        results.append((profile, digest))

    print("\n" + "=" * 70)
    print("QA COMPARISON REPORT")
    print("=" * 70)
    for profile, digest in results:
        print(f"\n--- {profile['district']} | {profile['email']} ---")
        print(f"Reasoning: {digest.leverage.reasoning_summary}")
        for i, rec in enumerate(digest.leverage.recommendations, 1):
            print(f"  REC {i}: {rec.action[:100]}")
            print(f"         type={rec.action_type} stage={rec.decision_stage} channel={rec.channel[:50]}")
        for item in digest.items:
            print(f"  ITEM: [{item.decision_stage}] {item.headline[:90]}")

    # Divergence check: recommendations should not be identical across profiles
    rec_sets = [
        {r.action[:60] for r in d.leverage.recommendations} for _, d in results
    ]
    overlap_all = rec_sets[0] & rec_sets[1] & rec_sets[2] if len(rec_sets) == 3 else set()
    print("\n" + "=" * 70)
    print(f"Recommendations identical across ALL profiles: {len(overlap_all)}")
    if overlap_all:
        print("Shared:", *[f"  - {a}" for a in overlap_all], sep="\n")
    print("(Some overlap is fine — e.g. the budget vote affects everyone — but")
    print(" rationales and channels should still differ by district/profile.)")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        main()
