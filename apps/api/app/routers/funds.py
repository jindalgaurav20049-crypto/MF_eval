"""
Fund endpoints — real implementation, reading from the database.

Replaces the original stub (3 hardcoded funds) with real queries against
data ingested by scripts/ingest_nav_data.py. See learning.md for the full
story of how that data got there — Tigzig, fuzzy-match bugs caught and
fixed, 73k+ real NAV rows.

Known gaps, flagged rather than hidden (see inline comments at each spot):
  - sub_category, option, aum_cr, expense_ratio_pct: not part of what we
    ingest yet — defaulted/None rather than faked.
  - "did it beat the index" / beta / capture ratios: need real benchmark
    (Nifty/Sensex) NAV history, which we don't have ingested — always None
    for now.
  - fund_health_score: uses a DELIBERATELY simple placeholder formula
    (see app/services/fund_metrics.py) — not a validated methodology.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import AMC, NAVHistoryDaily, Scheme
from app.models.schemas import (
    AdvancedSummary,
    AnalysisMode,
    BeginnerSummary,
    FundHealthScore,
    FundSearchResponse,
    FundSearchResult,
    ReturnMetrics,
    RiskMetrics,
)
from app.services.fund_metrics import (
    compute_metrics,
    load_nav_series,
    simple_health_score,
    trailing_window,
)

router = APIRouter(prefix="/funds", tags=["funds"])
logger = structlog.get_logger(__name__)


def _latest_nav(db: Session, scheme_id: int) -> float | None:
    row = (
        db.query(NAVHistoryDaily.nav)
        .filter_by(scheme_id=scheme_id)
        .order_by(NAVHistoryDaily.nav_date.desc())
        .first()
    )
    return float(row.nav) if row else None


def _to_search_result(db: Session, scheme: Scheme) -> FundSearchResult:
    return FundSearchResult(
        scheme_id=scheme.amfi_scheme_code,
        scheme_name=scheme.scheme_name,
        amc_name=scheme.amc.name,
        category=scheme.sebi_category or "Unknown",
        # Not ingested yet — ingest_nav_data.py only populates sebi_category
        sub_category=scheme.sebi_sub_category or "",
        plan=scheme.plan or "Direct",
        # Not ingested yet — every curated fund was confirmed as Growth
        # option during Session 6, but this isn't stored per-scheme, so
        # it's an assumption, not verified data. Flag, don't hide.
        option=scheme.option or "Growth",
        nav=_latest_nav(db, scheme.id),
        aum_cr=None,  # not ingested — no data source wired for this yet
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/search", response_model=FundSearchResponse)
async def search_funds(
    q: str = Query(..., min_length=1, description="Search query (scheme name, AMC, category)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> FundSearchResponse:
    """Search mutual fund schemes by name, AMC, or category — real DB query."""
    logger.info("fund_search", query=q, limit=limit)

    pattern = f"%{q}%"
    schemes = (
        db.query(Scheme)
        .join(AMC)
        .filter(
            or_(
                Scheme.scheme_name.ilike(pattern),
                AMC.name.ilike(pattern),
                Scheme.sebi_category.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )

    results = [_to_search_result(db, s) for s in schemes]
    return FundSearchResponse(query=q, total=len(results), results=results)


@router.get("/{scheme_id}/summary")
async def get_fund_summary(
    scheme_id: str,
    mode: AnalysisMode = Query(AnalysisMode.BEGINNER, description="Analysis mode: beginner | advanced"),
    db: Session = Depends(get_db),
) -> BeginnerSummary | AdvancedSummary:
    """
    Return fund summary computed live from real NAV data.

    - **beginner**: plain-language labels, core metrics, verdict chip
    - **advanced**: full metric matrix across 1Y/3Y/5Y windows
    """
    logger.info("fund_summary_requested", scheme_id=scheme_id, mode=mode)

    # scheme_id in the API is the AMFI code (a string), not the internal
    # integer PK — see learning.md Session 1 for why (AMFI codes are more
    # meaningful externally than an autoincrement ID).
    scheme = db.query(Scheme).filter_by(amfi_scheme_code=scheme_id).one_or_none()
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")

    series = load_nav_series(db, scheme.id)
    full = compute_metrics(series)
    health_score, confidence = simple_health_score(full)

    health = FundHealthScore(
        overall=health_score,
        # Sub-components need data we don't have yet (holdings quality,
        # governance, cost) — None rather than fabricated.
        returns_consistency=None,
        risk_containment=None,
        risk_adjusted_efficiency=None,
        portfolio_quality=None,
        stability_governance=None,
        cost_efficiency=None,
        confidence=confidence,
    )

    if mode == AnalysisMode.BEGINNER:
        window_3y = trailing_window(series, 3)
        metrics_3y = compute_metrics(window_3y)
        return BeginnerSummary(
            scheme_id=scheme_id,
            scheme_name=scheme.scheme_name,
            mode=AnalysisMode.BEGINNER,
            fund_health_score=health,
            yearly_growth_rate_3y=metrics_3y.cagr_pct,
            did_it_beat_index_3y=None,  # needs benchmark data — not ingested yet
            risk_level=_risk_level_label(full.std_dev_annualized_pct),
            expense_ratio_pct=None,  # not ingested yet
            fund_age_years=full.years_covered,
            verdict=_verdict_label(full),
            sip_note="Suitable for long-term wealth creation (5+ years horizon)"
            if full.years_covered >= 5
            else "Limited history available — review carefully before investing",
        )

    # Advanced mode — 1Y/3Y/5Y windows
    return_metrics = []
    for label, yrs in (("1Y", 1), ("3Y", 3), ("5Y", 5)):
        window = trailing_window(series, yrs)
        m = compute_metrics(window)
        return_metrics.append(
            ReturnMetrics(
                period=label,
                absolute_return_pct=None,
                cagr_pct=m.cagr_pct,
                vs_benchmark_pct=None,  # needs benchmark data
                vs_category_avg_pct=None,  # needs category-average computation
                category_percentile=None,  # needs all-funds-in-category ranking
            )
        )

    return AdvancedSummary(
        scheme_id=scheme_id,
        scheme_name=scheme.scheme_name,
        mode=AnalysisMode.ADVANCED,
        fund_health_score=health,
        return_metrics=return_metrics,
        risk_metrics=RiskMetrics(
            std_dev_annualized=full.std_dev_annualized_pct,
            beta=None,  # needs benchmark data
            max_drawdown_pct=full.max_drawdown_pct,
            downside_capture_ratio=None,  # needs benchmark data
            upside_capture_ratio=None,  # needs benchmark data
            sharpe_ratio=full.sharpe_ratio,
            sortino_ratio=None,  # analytics_engine has no Sortino implementation yet
        ),
        expense_ratio_pct=None,
        aum_cr=None,
        fund_age_years=full.years_covered,
        fund_manager=None,  # not ingested
        manager_tenure_years=None,  # not ingested
        benchmark=None,  # not wired up
        sebi_category=scheme.sebi_category,
    )


def _risk_level_label(std_dev: float | None) -> str | None:
    """Rough, transparent bucketing — not a validated risk methodology."""
    if std_dev is None:
        return None
    if std_dev < 5:
        return "Low"
    if std_dev < 12:
        return "Moderate"
    if std_dev < 20:
        return "Moderately High"
    return "High"


def _verdict_label(metrics) -> str:
    """Rough, transparent bucketing — not a validated verdict methodology."""
    if metrics.cagr_pct is None or metrics.sharpe_ratio is None:
        return "Insufficient Data"
    if metrics.cagr_pct >= 15 and metrics.sharpe_ratio >= 0.8:
        return "Strong"
    if metrics.cagr_pct >= 8 and metrics.sharpe_ratio >= 0.4:
        return "Average"
    return "Weak"