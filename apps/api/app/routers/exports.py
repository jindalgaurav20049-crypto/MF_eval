from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import UserPortfolioTxn
from app.db.session import get_db
from app.services.exports import (
    build_fund_summary_excel,
    build_fund_summary_pdf,
    build_portfolio_excel,
    build_portfolio_pdf,
)
from app.services.funds_service import (
    compute_and_store_metrics,
    ensure_mf_universe,
    ensure_nav_history,
    fetch_latest_metrics,
    get_scheme_by_code,
)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/funds/{scheme_id}/summary.xlsx")
async def export_fund_summary_excel(scheme_id: str, db: Session = Depends(get_db)) -> Response:
    summary = _fund_summary_data(db, scheme_id)
    payload = build_fund_summary_excel(summary)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={scheme_id}-summary.xlsx"},
    )


@router.get("/funds/{scheme_id}/summary.pdf")
async def export_fund_summary_pdf(scheme_id: str, db: Session = Depends(get_db)) -> Response:
    summary = _fund_summary_data(db, scheme_id)
    payload = build_fund_summary_pdf(summary)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={scheme_id}-summary.pdf"},
    )


@router.get("/portfolio/{user_id}.xlsx")
async def export_portfolio_excel(user_id: str, db: Session = Depends(get_db)) -> Response:
    entries = _portfolio_entries(db, user_id)
    payload = build_portfolio_excel(entries)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={user_id}-portfolio.xlsx"},
    )


@router.get("/portfolio/{user_id}.pdf")
async def export_portfolio_pdf(user_id: str, db: Session = Depends(get_db)) -> Response:
    entries = _portfolio_entries(db, user_id)
    payload = build_portfolio_pdf(entries)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={user_id}-portfolio.pdf"},
    )


def _fund_summary_data(db: Session, scheme_id: str) -> dict:
    ensure_mf_universe(db)
    scheme = get_scheme_by_code(db, scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    history = ensure_nav_history(db, scheme)
    metrics, risk_snapshot, health_score = fetch_latest_metrics(db, scheme)
    if not metrics and settings.auto_sync_metrics:
        metrics, risk_snapshot, health_score = compute_and_store_metrics(db, scheme, history)
    return {
        "scheme_id": scheme.amfi_scheme_code,
        "scheme_name": scheme.scheme_name,
        "category": scheme.sebi_category,
        "plan": scheme.plan,
        "option": scheme.option,
        "health_score": health_score,
        "latest_nav": history[-1][1] if history else None,
        "risk_std_dev": risk_snapshot.std_dev_annualized,
        "risk_sharpe": risk_snapshot.sharpe_ratio,
        "risk_drawdown": risk_snapshot.max_drawdown_pct,
    }


def _portfolio_entries(db: Session, user_id: str) -> list[dict]:
    txns = (
        db.execute(select(UserPortfolioTxn).where(UserPortfolioTxn.user_id == user_id))
        .scalars()
        .all()
    )
    return [
        {
            "scheme_id": txn.scheme_id,
            "txn_date": txn.txn_date.isoformat(),
            "txn_type": txn.txn_type,
            "amount": float(txn.amount) if txn.amount is not None else None,
            "units": float(txn.units) if txn.units is not None else None,
            "nav_at_txn": float(txn.nav_at_txn) if txn.nav_at_txn is not None else None,
        }
        for txn in txns
    ]
