"""Fund endpoints — stub implementations returning typed responses."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query

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

router = APIRouter(prefix="/funds", tags=["funds"])
logger = structlog.get_logger(__name__)

# ── Stub data helpers ─────────────────────────────────────────────────────────

_STUB_FUNDS: list[FundSearchResult] = [
    FundSearchResult(
        scheme_id="101206",
        scheme_name="Axis Bluechip Fund - Direct Plan Growth",
        amc_name="Axis Mutual Fund",
        category="Equity",
        sub_category="Large Cap",
        plan="Direct",
        option="Growth",
        nav=54.32,
        aum_cr=32500.0,
    ),
    FundSearchResult(
        scheme_id="119598",
        scheme_name="Mirae Asset Large Cap Fund - Direct Growth",
        amc_name="Mirae Asset Mutual Fund",
        category="Equity",
        sub_category="Large Cap",
        plan="Direct",
        option="Growth",
        nav=102.15,
        aum_cr=38200.0,
    ),
    FundSearchResult(
        scheme_id="120503",
        scheme_name="Parag Parikh Flexi Cap Fund - Direct Growth",
        amc_name="PPFAS Mutual Fund",
        category="Equity",
        sub_category="Flexi Cap",
        plan="Direct",
        option="Growth",
        nav=76.88,
        aum_cr=55000.0,
    ),
]

_STUB_HEALTH = FundHealthScore(
    overall=72.5,
    returns_consistency=75.0,
    risk_containment=68.0,
    risk_adjusted_efficiency=70.0,
    portfolio_quality=80.0,
    stability_governance=65.0,
    cost_efficiency=78.0,
    confidence="medium",
)


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/search", response_model=FundSearchResponse)
async def search_funds(
    q: str = Query(..., min_length=1, description="Search query (scheme name, AMC, category)"),
    limit: int = Query(20, ge=1, le=100),
) -> FundSearchResponse:
    """Search mutual fund schemes by name, AMC, or category."""
    logger.info("fund_search", query=q, limit=limit)

    # Stub: filter from in-memory list for demonstration
    q_lower = q.lower()
    results = [
        f
        for f in _STUB_FUNDS
        if q_lower in f.scheme_name.lower()
        or q_lower in f.amc_name.lower()
        or q_lower in f.category.lower()
    ][:limit]

    return FundSearchResponse(query=q, total=len(results), results=results)


@router.get("/{scheme_id}/summary")
async def get_fund_summary(
    scheme_id: str,
    mode: AnalysisMode = Query(AnalysisMode.BEGINNER, description="Analysis mode: beginner | advanced"),
) -> BeginnerSummary | AdvancedSummary:
    """
    Return fund summary. Mode controls verbosity and metric depth.

    - **beginner**: plain-language labels, 5 core metrics, verdict chip
    - **advanced**: full metric matrix, all windows, risk-adjusted ratios
    """
    logger.info("fund_summary_requested", scheme_id=scheme_id, mode=mode)

    # Stub: find fund or 404
    fund = next((f for f in _STUB_FUNDS if f.scheme_id == scheme_id), None)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")

    if mode == AnalysisMode.BEGINNER:
        return BeginnerSummary(
            scheme_id=scheme_id,
            scheme_name=fund.scheme_name,
            mode=AnalysisMode.BEGINNER,
            fund_health_score=_STUB_HEALTH,
            yearly_growth_rate_3y=12.4,
            did_it_beat_index_3y=True,
            risk_level="Moderately High",
            expense_ratio_pct=0.45,
            fund_age_years=9.5,
            verdict="Strong",
            sip_note="Suitable for long-term wealth creation (5+ years horizon)",
        )

    # Advanced mode
    return AdvancedSummary(
        scheme_id=scheme_id,
        scheme_name=fund.scheme_name,
        mode=AnalysisMode.ADVANCED,
        fund_health_score=_STUB_HEALTH,
        return_metrics=[
            ReturnMetrics(period="1Y", absolute_return_pct=18.2, vs_benchmark_pct=2.1, category_percentile=28),
            ReturnMetrics(period="3Y", cagr_pct=12.4, vs_benchmark_pct=1.8, category_percentile=32),
            ReturnMetrics(period="5Y", cagr_pct=14.1, vs_benchmark_pct=2.5, category_percentile=25),
        ],
        risk_metrics=RiskMetrics(
            std_dev_annualized=14.2,
            beta=0.93,
            max_drawdown_pct=-28.5,
            downside_capture_ratio=88.0,
            upside_capture_ratio=102.0,
            sharpe_ratio=0.82,
            sortino_ratio=1.12,
        ),
        expense_ratio_pct=0.45,
        aum_cr=fund.aum_cr,
        fund_age_years=9.5,
        fund_manager="Shreyash Devalkar",
        manager_tenure_years=7.2,
        benchmark="Nifty 100 TRI",
        sebi_category="Large Cap Fund",
    )
