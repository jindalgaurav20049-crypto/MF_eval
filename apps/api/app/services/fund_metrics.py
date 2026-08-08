"""
Real fund metrics — computed live from real ingested NAV data.

Shared by funds.py (search/summary) and, later, compare.py — one place
for this logic rather than duplicating it per-endpoint. Uses the actual
analytics_engine package (same code from Session 1 / demo_metrics.py),
nothing reimplemented here.

Deliberately independent of PR #2 (copilot/implement-phase-2-application)
per the decision in learning.md Session 4 — e.g. no Sortino ratio here,
since analytics_engine doesn't have one; better to return None honestly
than to bolt on unreviewed math to look more complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from analytics_engine import max_drawdown, sharpe_ratio
from analytics_engine.calculators.cagr import cagr_from_nav_series
from sqlalchemy.orm import Session

from app.db.models import NAVHistoryDaily


@dataclass
class NavPoint:
    nav_date: date
    nav: float


def load_nav_series(db: Session, scheme_id: int) -> list[NavPoint]:
    rows = (
        db.query(NAVHistoryDaily.nav_date, NAVHistoryDaily.nav)
        .filter_by(scheme_id=scheme_id)
        .order_by(NAVHistoryDaily.nav_date)
        .all()
    )
    return [NavPoint(nav_date=row.nav_date, nav=float(row.nav)) for row in rows]


def _daily_returns(navs: list[float]) -> list[float]:
    return [(navs[i] / navs[i - 1]) - 1 for i in range(1, len(navs))]


def trailing_window(series: list[NavPoint], years: float) -> list[NavPoint]:
    """Slice to the last N years of data. If the fund has less history
    than requested, returns whatever's actually available — caller should
    treat a short window as lower-confidence, not an error."""
    if not series:
        return []
    cutoff = series[-1].nav_date - timedelta(days=int(years * 365.25))
    return [p for p in series if p.nav_date >= cutoff]


@dataclass
class ComputedMetrics:
    years_covered: float
    cagr_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    std_dev_annualized_pct: float | None


def compute_metrics(series: list[NavPoint]) -> ComputedMetrics:
    """Compute CAGR/Sharpe/Drawdown/StdDev for a NAV series. Returns None
    for any metric that can't be computed responsibly (e.g. <2 data
    points) rather than a fabricated number — same "return None, don't
    guess" pattern as analytics_engine's own sharpe_ratio."""
    if len(series) < 2:
        return ComputedMetrics(0.0, None, None, None, None)

    navs = [p.nav for p in series]
    years = (series[-1].nav_date - series[0].nav_date).days / 365.25
    returns = _daily_returns(navs)

    fund_cagr = cagr_from_nav_series(navs, years=years) if years > 0 else None
    fund_sharpe = sharpe_ratio(returns, periods_per_year=252)
    fund_dd = max_drawdown(navs)

    std_dev_annualized = None
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std_dev_annualized = (variance ** 0.5) * (252 ** 0.5) * 100

    return ComputedMetrics(
        years_covered=years,
        cagr_pct=fund_cagr * 100 if fund_cagr is not None else None,
        sharpe_ratio=fund_sharpe,
        max_drawdown_pct=fund_dd * 100 if fund_dd is not None else None,
        std_dev_annualized_pct=std_dev_annualized,
    )


def simple_health_score(metrics: ComputedMetrics) -> tuple[float | None, str]:
    """A DELIBERATELY simple, transparent placeholder health score — not
    a validated methodology. Real health scoring (portfolio quality,
    governance, cost efficiency — see FundHealthScore's other fields)
    needs data we don't have yet (holdings, expense ratios, manager
    tenure). This only uses Sharpe + CAGR, scaled naively, and reports
    "low" confidence honestly rather than presenting a fake-precise number.
    Flagged here as a known placeholder, not hidden as if it were real.
    """
    if metrics.sharpe_ratio is None or metrics.cagr_pct is None:
        return None, "low"
    # Naive scaling: Sharpe of 1.0+ and CAGR of 15%+ -> high score.
    # This is NOT a validated formula — just a directional placeholder.
    sharpe_component = min(max(metrics.sharpe_ratio, 0), 2) / 2 * 50
    cagr_component = min(max(metrics.cagr_pct, 0), 25) / 25 * 50
    score = sharpe_component + cagr_component
    return round(score, 1), "low"