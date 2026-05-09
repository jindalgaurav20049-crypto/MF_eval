"""Fund endpoints backed by live MF universe data."""

from __future__ import annotations

from datetime import date

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FundManagerTenure
from app.db.session import get_db
from app.config import settings
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
from app.services.funds_service import (
    compute_and_store_metrics,
    ensure_mf_universe,
    ensure_nav_history,
    fetch_latest_metrics,
    get_scheme_by_code,
    search_schemes,
)
from app.services.metrics import rolling_returns

router = APIRouter(prefix="/funds", tags=["funds"])
logger = structlog.get_logger(__name__)


@router.get("/search", response_model=FundSearchResponse)
async def search_funds(
    q: str = Query(..., min_length=1, description="Search query (scheme name, AMC, category)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> FundSearchResponse:
    """Search mutual fund schemes by name, AMC, or category."""
    logger.info("fund_search", query=q, limit=limit)
    ensure_mf_universe(db)
    matches = search_schemes(db, q, limit)
    results = [
        FundSearchResult(
            scheme_id=scheme.amfi_scheme_code,
            scheme_name=scheme.scheme_name,
            amc_name=amc.name,
            category=scheme.sebi_category or "Uncategorized",
            sub_category=scheme.sebi_sub_category or "Unspecified",
            plan=scheme.plan or "Regular",
            option=scheme.option or "Growth",
            nav=float(nav) if nav is not None else None,
            aum_cr=None,
        )
        for scheme, amc, nav in matches
    ]
    return FundSearchResponse(query=q, total=len(results), results=results)


@router.get("/{scheme_id}/summary")
async def get_fund_summary(
    scheme_id: str,
    mode: AnalysisMode = Query(AnalysisMode.BEGINNER, description="Analysis mode: beginner | advanced"),
    db: Session = Depends(get_db),
) -> BeginnerSummary | AdvancedSummary:
    """
    Return fund summary. Mode controls verbosity and metric depth.

    - **beginner**: plain-language labels, 5 core metrics, verdict chip
    - **advanced**: full metric matrix, all windows, risk-adjusted ratios
    """
    logger.info("fund_summary_requested", scheme_id=scheme_id, mode=mode)
    ensure_mf_universe(db)
    scheme = get_scheme_by_code(db, scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")
    history = ensure_nav_history(db, scheme)
    metrics, risk_snapshot, health_score = fetch_latest_metrics(db, scheme)
    if not metrics and settings.auto_sync_metrics:
        metrics, risk_snapshot, health_score = compute_and_store_metrics(db, scheme, history)

    manager_name, tenure_years = _current_manager(db, scheme.id)
    fund_health = FundHealthScore(
        overall=health_score,
        returns_consistency=_score_band(health_score, 0.9),
        risk_containment=_score_band(health_score, 0.8),
        risk_adjusted_efficiency=_score_band(health_score, 0.85),
        portfolio_quality=None,
        stability_governance=None,
        cost_efficiency=None,
        confidence=_confidence_from_score(health_score),
    )

    if mode == AnalysisMode.BEGINNER:
        three_year = _metric_for_period(metrics, "3Y")
        return BeginnerSummary(
            scheme_id=scheme.amfi_scheme_code,
            scheme_name=scheme.scheme_name,
            mode=AnalysisMode.BEGINNER,
            fund_health_score=fund_health,
            yearly_growth_rate_3y=three_year.cagr_pct if three_year else None,
            did_it_beat_index_3y=None,
            risk_level=_risk_level(risk_snapshot.std_dev_annualized),
            expense_ratio_pct=None,
            fund_age_years=_fund_age_years(scheme.inception_date),
            verdict=_verdict_from_score(health_score),
            sip_note="Evaluate with a 5+ year horizon; diversify across categories.",
        )

    ordered_metrics = sorted(
        metrics,
        key=lambda metric: {"1Y": 1, "3Y": 2, "5Y": 3}.get(metric.period_label, 99),
    )
    return AdvancedSummary(
        scheme_id=scheme.amfi_scheme_code,
        scheme_name=scheme.scheme_name,
        mode=AnalysisMode.ADVANCED,
        fund_health_score=fund_health,
        return_metrics=[
            ReturnMetrics(
                period=metric.period_label,
                cagr_pct=metric.cagr_pct,
            )
            for metric in ordered_metrics
        ],
        risk_metrics=RiskMetrics(
            std_dev_annualized=risk_snapshot.std_dev_annualized,
            beta=None,
            max_drawdown_pct=risk_snapshot.max_drawdown_pct,
            downside_capture_ratio=None,
            upside_capture_ratio=None,
            sharpe_ratio=risk_snapshot.sharpe_ratio,
            sortino_ratio=risk_snapshot.sortino_ratio,
        ),
        expense_ratio_pct=None,
        aum_cr=None,
        fund_age_years=_fund_age_years(scheme.inception_date),
        fund_manager=manager_name,
        manager_tenure_years=tenure_years,
        benchmark=scheme.benchmark_name,
        sebi_category=scheme.sebi_category,
    )


@router.get("/{scheme_id}/rolling-returns")
async def get_rolling_returns(
    scheme_id: str,
    window_years: int = Query(3, ge=1, le=10, description="Rolling window in years"),
    db: Session = Depends(get_db),
) -> dict:
    ensure_mf_universe(db)
    scheme = get_scheme_by_code(db, scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")
    history = ensure_nav_history(db, scheme)
    series = rolling_returns(history, window_years=window_years)
    return {
        "scheme_id": scheme.amfi_scheme_code,
        "scheme_name": scheme.scheme_name,
        "window_years": window_years,
        "points": [
            {"date": nav_date.isoformat(), "return_pct": value} for nav_date, value in series
        ],
    }


def _current_manager(db: Session, scheme_id: int) -> tuple[str | None, float | None]:
    manager = db.execute(
        select(FundManagerTenure)
        .where(FundManagerTenure.scheme_id == scheme_id, FundManagerTenure.is_current.is_(True))
        .order_by(FundManagerTenure.start_date.desc())
    ).scalars().first()
    if manager is None:
        return None, None
    tenure_years = _fund_age_years(manager.start_date)
    return manager.manager_name, tenure_years


def _metric_for_period(metrics, label: str):
    for metric in metrics:
        if metric.period_label == label:
            return metric
    return None


def _risk_level(std_dev: float | None) -> str | None:
    if std_dev is None:
        return None
    if std_dev < 8:
        return "Low"
    if std_dev < 12:
        return "Moderate"
    if std_dev < 16:
        return "Moderately High"
    return "High"


def _fund_age_years(inception: date | None) -> float | None:
    if inception is None:
        return None
    return round((date.today() - inception).days / 365.25, 1)


def _verdict_from_score(score: float | None) -> str | None:
    if score is None:
        return "Insufficient Data"
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Average"
    return "Weak"


def _confidence_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _score_band(score: float | None, ratio: float) -> float | None:
    if score is None:
        return None
    return round(score * ratio, 2)
