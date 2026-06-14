"""SF campaign finance data from DataSF SODA API.

Fetches recent campaign contributions and expenditures for upcoming elections.
Surfaces who's funding what — critical context for ballot measures and races.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from ubl.models import RawArticle

logger = logging.getLogger(__name__)

TRANSACTIONS_URL = "https://data.sfgov.org/resource/pitq-e56w.json"
SUMMARY_URL = "https://data.sfgov.org/resource/9ggq-m8hp.json"


def fetch_campaign_finance(
    election_date: str | None = None,
    days_back: int = 14,
    min_amount: float = 10000,
    limit: int = 50,
) -> list[RawArticle]:
    """Fetch notable campaign finance transactions from DataSF.

    Surfaces large contributions/expenditures as RawArticle objects so they
    flow through the same pipeline. Only includes transactions above
    min_amount to avoid noise.
    """
    try:
        where_clauses = [f"transaction_amount_1 >= {min_amount}"]

        if election_date:
            where_clauses.append(f"election_date='{election_date}T00:00:00.000'")

        with httpx.Client(timeout=30) as client:
            resp = client.get(TRANSACTIONS_URL, params={
                "$limit": limit,
                "$order": "transaction_date DESC",
                "$where": " AND ".join(where_clauses),
            })
            resp.raise_for_status()

        data = resp.json()
        if not data:
            logger.info("No campaign finance transactions found")
            return []

        filer_totals: dict[str, dict] = {}
        for txn in data:
            filer = txn.get("filer_name", "Unknown")
            amount = float(txn.get("transaction_amount_1", 0))
            txn_date = txn.get("transaction_date", "")[:10]
            office = txn.get("office_sought_held", "")
            district = txn.get("district_number", "")
            form = txn.get("form_type", "")

            if filer not in filer_totals:
                filer_totals[filer] = {
                    "total": 0,
                    "count": 0,
                    "latest_date": txn_date,
                    "office": office,
                    "district": district,
                    "form": form,
                    "transactions": [],
                }

            filer_totals[filer]["total"] += amount
            filer_totals[filer]["count"] += 1
            if txn_date > filer_totals[filer]["latest_date"]:
                filer_totals[filer]["latest_date"] = txn_date
            filer_totals[filer]["transactions"].append({
                "amount": amount,
                "date": txn_date,
                "description": txn.get("transaction_description", ""),
            })

        articles: list[RawArticle] = []
        for filer, info in sorted(
            filer_totals.items(), key=lambda x: x[1]["total"], reverse=True
        ):
            total = info["total"]
            count = info["count"]
            latest = info["latest_date"]

            title = f"[Campaign Finance] {filer}: ${total:,.0f} in {count} transaction{'s' if count > 1 else ''}"

            content_lines = [
                f"Filer: {filer}",
                f"Total: ${total:,.0f}",
                f"Transactions: {count}",
                f"Latest: {latest}",
            ]
            if info["office"]:
                content_lines.append(f"Office: {info['office']}")
            if info["district"]:
                content_lines.append(f"District: {info['district']}")

            content_lines.append("\nRecent transactions:")
            for txn in info["transactions"][:5]:
                desc = txn["description"] or "contribution/expenditure"
                content_lines.append(
                    f"  ${txn['amount']:,.0f} on {txn['date']} — {desc}"
                )

            try:
                pub_dt = datetime.strptime(latest, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pub_dt = datetime.now(timezone.utc)

            articles.append(
                RawArticle(
                    source="datasf_campaign_finance",
                    title=title,
                    url=f"https://sfethics.org/disclosures/campaign-finance-disclosure#{filer.replace(' ', '-')}",
                    content="\n".join(content_lines),
                    published_at=pub_dt,
                )
            )

        logger.info(
            "Fetched %d campaign finance summaries (%d transactions, $%s total)",
            len(articles),
            len(data),
            f"{sum(i['total'] for i in filer_totals.values()):,.0f}",
        )
        return articles

    except Exception:
        logger.exception("Failed to fetch campaign finance data")
        return []
