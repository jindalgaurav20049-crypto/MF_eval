"""Compare endpoint backed by live MF data."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.schemas import (
    AnalysisMode,
    CompareResponse,
    CompareSchemeSlot,
)
from app.services.funds_service import (
    compute_and_store_metrics,
    ensure_mf_universe,
    ensure_nav_history,
    fetch_latest_metrics,
    get_scheme_by_code,
)
from app.services.metrics import metric_for_period

router = APIRouter(prefix="/compare", tags=["compare"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=CompareResponse)
async def compare_funds(
    scheme_ids: str = Query(..., description="Comma-separated scheme IDs (2–5 funds)"),
    mode: AnalysisMode = Query(AnalysisMode.BEGINNER),
    db: Session = Depends(get_db),
) -> CompareResponse:
    """Compare up to 5 mutual fund schemes side by side."""
    ids = [s.strip() for s in scheme_ids.split(",") if s.strip()]
    logger.info("compare_funds_requested", scheme_ids=ids, mode=mode)

    ensure_mf_universe(db)
    slots: list[CompareSchemeSlot] = []
    for scheme_code in ids:
        scheme = get_scheme_by_code(db, scheme_code)
        if scheme is None:
            continue
        history = ensure_nav_history(db, scheme)
        metrics, risk_snapshot, health_score = fetch_latest_metrics(db, scheme)
        if not metrics and settings.auto_sync_metrics:
            metrics, risk_snapshot, health_score = compute_and_store_metrics(db, scheme, history)
        one_year = metric_for_period(metrics, "1Y")
        three_year = metric_for_period(metrics, "3Y")
        five_year = metric_for_period(metrics, "5Y")
        latest_nav = history[-1][1] if history else None
        slots.append(
            CompareSchemeSlot(
                scheme_id=scheme.amfi_scheme_code,
                scheme_name=scheme.scheme_name,
                category=scheme.sebi_category or "Uncategorized",
                expense_ratio_pct=None,
                nav=latest_nav,
                return_1y_pct=one_year.cagr_pct if one_year else None,
                return_3y_cagr_pct=three_year.cagr_pct if three_year else None,
                return_5y_cagr_pct=five_year.cagr_pct if five_year else None,
                std_dev_3y=three_year.std_dev_annualized if three_year else None,
                sharpe_3y=three_year.sharpe_ratio if three_year else None,
                max_drawdown_pct=three_year.max_drawdown_pct if three_year else None,
                fund_health_score=health_score,
            )
        )

    note = None
    if mode == AnalysisMode.BEGINNER and len(slots) > 2:
        note = "Beginner mode shows up to 2 funds side-by-side for clarity."
        slots = slots[:2]

    return CompareResponse(mode=mode, schemes=slots, note=note)
