"""
Scheme code lookup — Phase A, step 1.

Resolves real AMFI scheme codes for our curated starter list of ~24 funds
by querying Tigzig's MF NAV API search endpoint (https://api.tigzig.com/mf/v1/).
This exists because the scheme codes currently hardcoded in
apps/api/app/routers/funds.py and compare.py are placeholders and do NOT
match real AMFI codes (verified during planning — see learning.md Session 2)
— we don't want to repeat that mistake by guessing codes from memory again.

Why Tigzig over mfapi.in (see learning.md Session 4 for the full comparison):
NAVs come back as numbers (not strings), search + history + batch NAV live
under one consistent API, and the NAV endpoint accepts up to 50 scheme codes
in a single call — handy for Phase A's actual ingestion step, once codes are
confirmed here.

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

TIGZIG_SEARCH_URL = "https://api.tigzig.com/mf/v1/search"
SLEEP_BETWEEN_CALLS_SECONDS = 0.05  # Tigzig allows 300 req/min/IP — light delay is plenty
OUTPUT_PATH = Path(__file__).parent / "resolved_schemes.json"

# Curated starter list: ~3 funds per category, chosen for name recognition
# and category variety (see learning.md Session 2 for why these categories).
# NOTE: these are *search terms*, not scheme codes — the whole point of this
# script is that we don't trust hand-typed scheme codes anymore.
CURATED_FUNDS: list[dict[str, str]] = [
    # Large Cap
    {"category": "Large Cap", "amc": "Axis Mutual Fund", "search": "Axis Large Cap Fund Direct Growth"},  # renamed from Axis Bluechip Fund, June 2025
    {"category": "Large Cap", "amc": "Mirae Asset Mutual Fund", "search": "Mirae Asset Large Cap Fund Direct Growth"},
    {"category": "Large Cap", "amc": "ICICI Prudential Mutual Fund", "search": "ICICI Prudential Bluechip Fund Direct Growth"},
    # Flexi Cap
    {"category": "Flexi Cap", "amc": "PPFAS Mutual Fund", "search": "Parag Parikh Flexi Cap Fund Direct Growth"},
    {"category": "Flexi Cap", "amc": "HDFC Mutual Fund", "search": "HDFC Flexi Cap Fund Direct Growth"},
    {"category": "Flexi Cap", "amc": "Kotak Mahindra Mutual Fund", "search": "Kotak Flexicap Fund Direct Growth"},
    # Mid Cap
    {"category": "Mid Cap", "amc": "Kotak Mahindra Mutual Fund", "search": "Kotak Emerging Equity"},  # simplified — "...Fund Direct Growth" returned no matches, worth rechecking for a rename too
    {"category": "Mid Cap", "amc": "Axis Mutual Fund", "search": "Axis Midcap Fund Direct Growth"},
    {"category": "Mid Cap", "amc": "PGIM India Mutual Fund", "search": "PGIM India Midcap Fund Direct Growth"},  # renamed from PGIM India Midcap Opportunities Fund
    # Small Cap
    {"category": "Small Cap", "amc": "Nippon India Mutual Fund", "search": "Nippon India Small Cap Fund Direct Growth"},
    {"category": "Small Cap", "amc": "SBI Mutual Fund", "search": "SBI Small Cap Fund Direct Growth"},
    {"category": "Small Cap", "amc": "Axis Mutual Fund", "search": "Axis Small Cap Fund Direct Growth"},
    # ELSS (tax-saving)
    {"category": "ELSS", "amc": "Axis Mutual Fund", "search": "Axis ELSS Tax Saver Fund Direct Growth"},  # renamed from Axis Long Term Equity Fund, Dec 2023
    {"category": "ELSS", "amc": "Mirae Asset Mutual Fund", "search": "Mirae Asset Tax Saver Fund Direct Growth"},
    {"category": "ELSS", "amc": "Quant Mutual Fund", "search": "Quant Tax Plan Direct Growth"},
    # Debt — Short Duration
    {"category": "Debt Short Duration", "amc": "HDFC Mutual Fund", "search": "HDFC Short Term Debt Fund Direct Growth"},
    {"category": "Debt Short Duration", "amc": "ICICI Prudential Mutual Fund", "search": "ICICI Prudential Short Term Fund Direct Growth"},
    {"category": "Debt Short Duration", "amc": "Axis Mutual Fund", "search": "Axis Short Duration Fund Direct Growth"},  # renamed from Axis Short Term Fund
    # Hybrid / Balanced Advantage
    {"category": "Hybrid - Balanced Advantage", "amc": "ICICI Prudential Mutual Fund", "search": "ICICI Prudential Balanced Advantage Fund Direct Growth"},
    {"category": "Hybrid - Balanced Advantage", "amc": "HDFC Mutual Fund", "search": "HDFC Balanced Advantage Fund Direct Growth"},
    {"category": "Hybrid - Balanced Advantage", "amc": "Edelweiss Mutual Fund", "search": "Edelweiss Balanced Advantage Fund Direct Growth"},
    # Index Fund (useful as an in-app benchmark)
    {"category": "Index Fund", "amc": "UTI Mutual Fund", "search": "UTI Nifty 50 Index Fund Direct Growth"},
    {"category": "Index Fund", "amc": "HDFC Mutual Fund", "search": "HDFC Index Fund Nifty 50 Direct Growth"},
    {"category": "Index Fund", "amc": "ICICI Prudential Mutual Fund", "search": "ICICI Prudential Nifty 50 Index Fund Direct Growth"},
]


def _normalize(name: str) -> str:
    """Lowercase and strip punctuation for fuzzy comparison."""
    return "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in name).strip()


def _scheme_name(candidate: dict) -> str:
    """Tigzig's confirmed field is scheme_name (snake_case, verified live
    against the /nav endpoint). Fall back to a couple of plausible variants
    in case /search differs — worth confirming on your first real run and
    simplifying this once confirmed."""
    return candidate.get("scheme_name") or candidate.get("schemeName") or ""


def search_tigzig(query: str) -> list[dict]:
    """Call Tigzig's search endpoint. Returns [] on any failure (network,
    non-200, bad JSON) rather than raising — one bad lookup shouldn't kill
    the whole batch."""
    try:
        resp = requests.get(TIGZIG_SEARCH_URL, params={"q": query}, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        # Response may be a bare list or wrapped under a "results"/"data" key
        # — handle both until confirmed by a real run.
        if isinstance(data, dict):
            data = data.get("results") or data.get("data") or data.get("schemes") or []
        return data
    except (requests.RequestException, ValueError) as exc:
        print(f"  ! search failed for {query!r}: {exc}")
        return []


def rank_candidates(search_term: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    """Rank Tigzig's raw results by string similarity to our search term,
    so the human reviewer sees the most likely match first."""
    target = _normalize(search_term)
    scored = [
        {
            **c,
            "match_score": difflib.SequenceMatcher(
                None, target, _normalize(_scheme_name(c))
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
        raw = search_tigzig(fund["search"])
        top = rank_candidates(fund["search"], raw)

        results.append(
            {
                "category": fund["category"],
                "amc": fund["amc"],
                "search_term": fund["search"],
                "candidates": top,
                # Deliberately null, even when top[0] looks right. Session 6
                # found 7/24 auto-picked top candidates were the WRONG fund
                # entirely (e.g. "Quant Tax Plan" auto-matched "Quantum ELSS
                # Tax Saver Fund" — a different AMC). ingest_nav_data.py
                # refuses to use any entry where this is still null — a human
                # must copy the correct scheme_code here after checking it's
                # actually the right fund, not just the highest text-similarity
                # score.
                "confirmed_scheme_code": None,
            }
        )

        if not top:
            print("  ! no candidates found — will need manual lookup on tigzig.com")

        time.sleep(SLEEP_BETWEEN_CALLS_SECONDS)

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} entries to {OUTPUT_PATH}")
    print("Next: open the file. For EACH entry, check the candidates against")
    print("the fund's real name/category, then set confirmed_scheme_code to")
    print("the correct one. ingest_nav_data.py will skip any entry left null.")


if __name__ == "__main__":
    main()