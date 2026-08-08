"""
Demo — Phase A, proof of concept: real data -> real metrics.

This is the demo script for showing the pipeline actually works:
  1. Pull real NAV history for every ingested fund from the database
  2. Feed it into the ACTUAL analytics_engine package (the same tested
     CAGR/Sharpe/Drawdown functions from Session 1 — nothing reimplemented
     here) — not a mock, not hardcoded numbers
  3. Print a clean comparison table across all real funds

Nothing about this is faked or simplified for the demo: it's the same
database, same math library, same code that Phase B/C will build on.

Usage:
    python scripts/demo_metrics.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

API_APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_APP_ROOT))

from app.db.base import SessionLocal  # noqa: E402
from app.db.models import NAVHistoryDaily, Scheme  # noqa: E402
from analytics_engine import max_drawdown, sharpe_ratio  # noqa: E402
from analytics_engine.calculators.cagr import cagr_from_nav_series  # noqa: E402


def load_nav_series(session, scheme_id: int) -> list[tuple[date, float]]:
    rows = (
        session.query(NAVHistoryDaily.nav_date, NAVHistoryDaily.nav)
        .filter_by(scheme_id=scheme_id)
        .order_by(NAVHistoryDaily.nav_date)
        .all()
    )
    return [(row.nav_date, float(row.nav)) for row in rows]


def daily_returns(navs: list[float]) -> list[float]:
    return [(navs[i] / navs[i - 1]) - 1 for i in range(1, len(navs))]


def main() -> None:
    session = SessionLocal()
    try:
        schemes = session.query(Scheme).order_by(Scheme.sebi_category, Scheme.scheme_name).all()

        print(f"{'Fund':<55} {'Category':<22} {'Years':>6} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8}")
        print("-" * 112)

        for scheme in schemes:
            series = load_nav_series(session, scheme.id)
            if len(series) < 2:
                print(f"{scheme.scheme_name:<55} {scheme.sebi_category:<22}   (insufficient data)")
                continue

            navs = [nav for _, nav in series]
            years = (series[-1][0] - series[0][0]).days / 365.25

            fund_cagr = cagr_from_nav_series(navs, years=years) if years > 0 else None
            fund_dd = max_drawdown(navs)
            fund_sharpe = sharpe_ratio(daily_returns(navs), periods_per_year=252)

            cagr_str = f"{fund_cagr:+.1%}" if fund_cagr is not None else "N/A"
            sharpe_str = f"{fund_sharpe:.2f}" if fund_sharpe is not None else "N/A"
            dd_str = f"{fund_dd:.1%}"
            name = scheme.scheme_name[:53]

            print(f"{name:<55} {scheme.sebi_category:<22} {years:>6.1f} {cagr_str:>8} {sharpe_str:>8} {dd_str:>8}")

        print("-" * 112)
        print(f"\n{len(schemes)} funds — real NAV history ingested via Tigzig, real metrics via analytics_engine.")
    finally:
        session.close()


if __name__ == "__main__":
    main()