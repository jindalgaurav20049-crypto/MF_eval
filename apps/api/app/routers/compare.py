"""
Compare endpoint — real implementation, reusing app/services/fund_metrics.py
(same computation used by funds.py's summary endpoint — one source of truth).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Scheme
from app.models.schemas import AnalysisMode, CompareResponse, CompareSchemeSlot
from app.services.fund_metrics import (
    compute_metrics,
    load_nav_series,
    simple_health_score,
    trailing_window,
)

router = APIRouter(prefix="/compare", tags=["compare"])
logger = structlog.get_logger(__name__)


def _absolute_return_pct(series, years: float) -> float | None:
    """Simple absolute % change over a trailing window — different from
    CAGR, which annualizes. For a 1Y window these are close but not
    identical; for consistency with what "1Y return" means to most fund
    websites, this uses plain absolute change, not CAGR."""
    window = trailing_window(series, years)
    if len(window) < 2:
        return None
    return (window[-1].nav / window[0].nav - 1) * 100


def _build_slot(db: Session, scheme: Scheme) -> CompareSchemeSlot:
    series = load_nav_series(db, scheme.id)
    full = compute_metrics(series)
    health_score, _ = simple_health_score(full)
    latest_nav = float(series[-1].nav) if series else None

    metrics_3y = compute_metrics(trailing_window(series, 3))
    metrics_5y = compute_metrics(trailing_window(series, 5))

    return CompareSchemeSlot(
        scheme_id=scheme.amfi_scheme_code,
        scheme_name=scheme.scheme_name,
        category=scheme.sebi_category or "Unknown",
        expense_ratio_pct=None,  # not ingested yet
        nav=latest_nav,
        return_1y_pct=_absolute_return_pct(series, 1),
        return_3y_cagr_pct=metrics_3y.cagr_pct,
        return_5y_cagr_pct=metrics_5y.cagr_pct,
        # These fields are named "_3y" in the schema — use the 3Y window's
        # values, not full-history (caught while fixing return_3y_cagr_pct
        # above; same underlying oversight).
        std_dev_3y=metrics_3y.std_dev_annualized_pct,
        sharpe_3y=metrics_3y.sharpe_ratio,
        max_drawdown_pct=full.max_drawdown_pct,  # this one IS meant to be full-history
        fund_health_score=health_score,
    )


@router.get("", response_model=CompareResponse)
async def compare_funds(
    scheme_ids: str = Query(..., description="Comma-separated scheme IDs (2–5 funds)"),
    mode: AnalysisMode = Query(AnalysisMode.BEGINNER),
    db: Session = Depends(get_db),
) -> CompareResponse:
    """Compare up to 5 mutual fund schemes side by side — real DB query."""
    ids = [s.strip() for s in scheme_ids.split(",") if s.strip()]
    logger.info("compare_funds_requested", scheme_ids=ids, mode=mode)

    schemes = db.query(Scheme).filter(Scheme.amfi_scheme_code.in_(ids)).all()
    # Preserve the order the caller asked for, skip any ID that wasn't found
    by_code = {s.amfi_scheme_code: s for s in schemes}
    slots = [_build_slot(db, by_code[sid]) for sid in ids if sid in by_code]

    note = None
    if mode == AnalysisMode.BEGINNER and len(slots) > 2:
        note = "Beginner mode shows up to 2 funds side-by-side for clarity."
        slots = slots[:2]

    return CompareResponse(mode=mode, schemes=slots, note=note)