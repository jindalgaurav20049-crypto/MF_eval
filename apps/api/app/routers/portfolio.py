from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.portfolio import (
    compute_portfolio_overlap,
    compute_tax_scenarios,
    import_holdings_snapshot,
    import_portfolio_transactions,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
logger = structlog.get_logger(__name__)


@router.post("/import/cas")
async def import_cas(
    email: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    payload = await file.read()
    logger.info("portfolio_cas_import", email=email, filename=file.filename)
    result = import_portfolio_transactions(db, email, file.filename or "cas.csv", payload)
    return {
        "user_id": result.user_id,
        "transactions_loaded": result.transactions_loaded,
        "schemes_updated": result.schemes_updated,
    }


@router.post("/holdings/import")
async def import_holdings(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    payload = await file.read()
    logger.info("portfolio_holdings_import", filename=file.filename)
    count = import_holdings_snapshot(db, payload)
    return {"rows_loaded": count}


@router.get("/{user_id}/overlap")
async def portfolio_overlap(user_id: str, db: Session = Depends(get_db)) -> dict:
    overlap = compute_portfolio_overlap(db, user_id)
    return {"user_id": user_id, "overlap": overlap}


@router.get("/{user_id}/tax")
async def portfolio_tax(user_id: str, db: Session = Depends(get_db)) -> dict:
    scenarios = compute_tax_scenarios(db, user_id)
    return {"user_id": user_id, "tax_scenarios": scenarios}
