"""Compare endpoint — stub returning typed response."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Query

from app.models.schemas import (
    AnalysisMode,
    CompareResponse,
    CompareSchemeSlot,
)

router = APIRouter(prefix="/compare", tags=["compare"])
logger = structlog.get_logger(__name__)

_STUB_SLOTS: dict[str, CompareSchemeSlot] = {
    "101206": CompareSchemeSlot(
        scheme_id="101206",
        scheme_name="Axis Bluechip Fund - Direct Plan Growth",
        category="Large Cap",
        expense_ratio_pct=0.45,
        nav=54.32,
        return_1y_pct=18.2,
        return_3y_cagr_pct=12.4,
        return_5y_cagr_pct=14.1,
        std_dev_3y=14.2,
        sharpe_3y=0.82,
        max_drawdown_pct=-28.5,
        fund_health_score=72.5,
    ),
    "119598": CompareSchemeSlot(
        scheme_id="119598",
        scheme_name="Mirae Asset Large Cap Fund - Direct Growth",
        category="Large Cap",
        expense_ratio_pct=0.52,
        nav=102.15,
        return_1y_pct=19.8,
        return_3y_cagr_pct=13.1,
        return_5y_cagr_pct=15.3,
        std_dev_3y=13.8,
        sharpe_3y=0.91,
        max_drawdown_pct=-26.2,
        fund_health_score=76.0,
    ),
    "120503": CompareSchemeSlot(
        scheme_id="120503",
        scheme_name="Parag Parikh Flexi Cap Fund - Direct Growth",
        category="Flexi Cap",
        expense_ratio_pct=0.61,
        nav=76.88,
        return_1y_pct=22.3,
        return_3y_cagr_pct=15.6,
        return_5y_cagr_pct=17.2,
        std_dev_3y=12.1,
        sharpe_3y=1.14,
        max_drawdown_pct=-22.1,
        fund_health_score=82.0,
    ),
}


@router.get("", response_model=CompareResponse)
async def compare_funds(
    scheme_ids: str = Query(..., description="Comma-separated scheme IDs (2–5 funds)"),
    mode: AnalysisMode = Query(AnalysisMode.BEGINNER),
) -> CompareResponse:
    """Compare up to 5 mutual fund schemes side by side."""
    ids = [s.strip() for s in scheme_ids.split(",") if s.strip()]
    logger.info("compare_funds_requested", scheme_ids=ids, mode=mode)

    slots = [_STUB_SLOTS[sid] for sid in ids if sid in _STUB_SLOTS]

    note = None
    if mode == AnalysisMode.BEGINNER and len(slots) > 2:
        note = "Beginner mode shows up to 2 funds side-by-side for clarity."
        slots = slots[:2]

    return CompareResponse(mode=mode, schemes=slots, note=note)
