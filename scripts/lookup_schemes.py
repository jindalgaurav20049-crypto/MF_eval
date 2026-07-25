"""
Scheme code lookup — Phase A, step 1.

Resolves real AMFI scheme codes for our curated starter list of ~24 funds
by querying mfapi.in's search endpoint. This exists because the scheme
codes currently hardcoded in apps/api/app/routers/funds.py and compare.py
are placeholders and do NOT match real AMFI codes (verified during
planning — see learning.md Session 2) — we don't want to repeat that
mistake by guessing codes from memory again.

This script is meant to be run locally (it needs real internet access,
which the dev sandbox that helped write it does not have). It does NOT
write to the database — it just produces a reviewed JSON file
(resolved_schemes.json) that a human checks before Phase A's ingestion
script consumes it.

Usage:
    pip install requests
    python scripts/lookup_schemes.py

Output:
    scripts/resolved_schemes.json — one entry per fund, with the top
    candidate matches for a human to confirm/pick from.
"""

from __future__ import annotations

import difflib
import json
import time
from pathlib import Path

import requests

MFAPI_SEARCH_URL = "https://api.mfapi.in/mf/search"
SLEEP_BETWEEN_CALLS_SECONDS = 0.3  # be polite to a free public API
OUTPUT_PATH = Path(__file__).parent / "resolved_schemes.json"

# Curated starter list: ~3 funds per category, chosen for name recognition
# and category variety (see learning.md Session 2 for why these categories).
# NOTE: these are *search terms*, not scheme codes — the whole point of this
# script is that we don't trust hand-typed scheme codes anymore.
CURATED_FUNDS: list[dict[str, str]] = [
    # Large Cap
    {"category": "Large Cap", "search": "Axis Bluechip Fund Direct Growth"},
    {"category": "Large Cap", "search": "Mirae Asset Large Cap Fund Direct Growth"},
    {"category": "Large Cap", "search": "ICICI Prudential Bluechip Fund Direct Growth"},
    # Flexi Cap
    {"category": "Flexi Cap", "search": "Parag Parikh Flexi Cap Fund Direct Growth"},
    {"category": "Flexi Cap", "search": "HDFC Flexi Cap Fund Direct Growth"},
    {"category": "Flexi Cap", "search": "Kotak Flexicap Fund Direct Growth"},
    # Mid Cap
    {"category": "Mid Cap", "search": "Kotak Emerging Equity Fund Direct Growth"},
    {"category": "Mid Cap", "search": "Axis Midcap Fund Direct Growth"},
    {"category": "Mid Cap", "search": "PGIM India Midcap Opportunities Fund Direct Growth"},
    # Small Cap
    {"category": "Small Cap", "search": "Nippon India Small Cap Fund Direct Growth"},
    {"category": "Small Cap", "search": "SBI Small Cap Fund Direct Growth"},
    {"category": "Small Cap", "search": "Axis Small Cap Fund Direct Growth"},
    # ELSS (tax-saving)
    {"category": "ELSS", "search": "Axis Long Term Equity Fund Direct Growth"},
    {"category": "ELSS", "search": "Mirae Asset Tax Saver Fund Direct Growth"},
    {"category": "ELSS", "search": "Quant Tax Plan Direct Growth"},
    # Debt — Short Duration
    {"category": "Debt Short Duration", "search": "HDFC Short Term Debt Fund Direct Growth"},
    {"category": "Debt Short Duration", "search": "ICICI Prudential Short Term Fund Direct Growth"},
    {"category": "Debt Short Duration", "search": "Axis Short Term Fund Direct Growth"},
    # Hybrid / Balanced Advantage
    {"category": "Hybrid - Balanced Advantage", "search": "ICICI Prudential Balanced Advantage Fund Direct Growth"},
    {"category": "Hybrid - Balanced Advantage", "search": "HDFC Balanced Advantage Fund Direct Growth"},
    {"category": "Hybrid - Balanced Advantage", "search": "Edelweiss Balanced Advantage Fund Direct Growth"},
    # Index Fund (useful as an in-app benchmark)
    {"category": "Index Fund", "search": "UTI Nifty 50 Index Fund Direct Growth"},
    {"category": "Index Fund", "search": "HDFC Index Fund Nifty 50 Direct Growth"},
    {"category": "Index Fund", "search": "ICICI Prudential Nifty 50 Index Fund Direct Growth"},
]


def _normalize(name: str) -> str:
    """Lowercase and strip punctuation for fuzzy comparison."""
    return "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in name).strip()


def search_mfapi(query: str) -> list[dict]:
    """Call mfapi.in's search endpoint. Returns [] on any failure (network,
    non-200, bad JSON) rather than raising — one bad lookup shouldn't kill
    the whole batch."""
    try:
        resp = requests.get(MFAPI_SEARCH_URL, params={"q": query}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  ! search failed for {query!r}: {exc}")
        return []


def rank_candidates(search_term: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    """Rank mfapi's raw results by string similarity to our search term,
    so the human reviewer sees the most likely match first."""
    target = _normalize(search_term)
    scored = [
        {
            **c,
            "match_score": difflib.SequenceMatcher(
                None, target, _normalize(c.get("schemeName", ""))
            ).ratio(),
        }
        for c in candidates
    ]
    scored.sort(key=lambda c: c["match_score"], reverse=True)
    return scored[:top_n]


def main() -> None:
    results = []
    for fund in CURATED_FUNDS:
        print(f"Looking up: {fund['search']}")
        raw = search_mfapi(fund["search"])
        top = rank_candidates(fund["search"], raw)

        results.append(
            {
                "category": fund["category"],
                "search_term": fund["search"],
                "candidates": top,  # human picks the right one; do not auto-accept
            }
        )

        if not top:
            print("  ! no candidates found — will need manual lookup on mfapi.in")

        time.sleep(SLEEP_BETWEEN_CALLS_SECONDS)

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} entries to {OUTPUT_PATH}")
    print("Next: open the file, confirm each match by eye, and drop any")
    print("wrong/ambiguous ones into a follow-up manual-lookup pass.")


if __name__ == "__main__":
    main()