from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AMC, ComputedMetricSnapshot, NAVHistoryDaily, Scheme
from app.services.ingestion import SyncResult, sync_mf_universe, update_scheme_from_detail
from app.services.metrics import (
    RiskSnapshot,
    TrailingMetric,
    compute_fund_health,
    compute_risk_snapshot,
    compute_trailing_metrics,
)
from app.services.mfapi_client import MFAPIClient


def ensure_mf_universe(db: Session) -> SyncResult:
    existing = db.execute(select(func.count()).select_from(Scheme)).scalar_one()
    if existing == 0 and settings.auto_sync_mf_universe:
        return sync_mf_universe(db)
    return SyncResult(schemes_added=0, schemes_updated=0, nav_rows_added=0)


def search_schemes(db: Session, query: str, limit: int) -> list[tuple[Scheme, AMC, Decimal | None]]:
    subq = (
        select(
            NAVHistoryDaily.scheme_id,
            func.max(NAVHistoryDaily.nav_date).label("max_date"),
        )
        .group_by(NAVHistoryDaily.scheme_id)
        .subquery()
    )
    nav_alias = NAVHistoryDaily
    stmt = (
        select(Scheme, AMC, nav_alias.nav)
        .join(AMC, AMC.id == Scheme.amc_id)
        .outerjoin(subq, subq.c.scheme_id == Scheme.id)
        .outerjoin(
            nav_alias,
            (nav_alias.scheme_id == Scheme.id) & (nav_alias.nav_date == subq.c.max_date),
        )
        .where(
            or_(
                Scheme.scheme_name.ilike(f"%{query}%"),
                AMC.name.ilike(f"%{query}%"),
                Scheme.sebi_category.ilike(f"%{query}%"),
                Scheme.sebi_sub_category.ilike(f"%{query}%"),
            )
        )
        .order_by(Scheme.scheme_name.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).all())


def get_scheme_by_code(db: Session, scheme_code: str) -> Scheme | None:
    return db.execute(
        select(Scheme).where(Scheme.amfi_scheme_code == scheme_code)
    ).scalar_one_or_none()


def ensure_nav_history(db: Session, scheme: Scheme) -> list[tuple[date, float]]:
    history = [
        (row.nav_date, float(row.nav))
        for row in db.execute(
            select(NAVHistoryDaily)
            .where(NAVHistoryDaily.scheme_id == scheme.id)
            .order_by(NAVHistoryDaily.nav_date.asc())
        ).scalars()
    ]
    if history:
        return history
    if not settings.auto_sync_navs:
        return history
    client = MFAPIClient()
    try:
        detail = client.fetch_scheme_detail(scheme.amfi_scheme_code)
    finally:
        client.close()
    if detail is None:
        return history
    update_scheme_from_detail(db, scheme, detail)
    db.commit()
    history = detail.nav_history
    if history:
        from app.services.ingestion import store_nav_history

        store_nav_history(db, scheme.id, history)
    return history


def compute_and_store_metrics(
    db: Session,
    scheme: Scheme,
    history: list[tuple[date, float]],
) -> tuple[list[TrailingMetric], RiskSnapshot, float | None]:
    metrics = compute_trailing_metrics(history)
    risk = compute_risk_snapshot(history)
    health = compute_fund_health(metrics)
    if not metrics:
        return metrics, risk, health

    latest_date = max(row[0] for row in history)
    computed_at = datetime.combine(latest_date, datetime.min.time())
    for metric in metrics:
        snapshot = ComputedMetricSnapshot(
            scheme_id=scheme.id,
            period_label=metric.period_label,
            computed_at=computed_at,
            cagr_pct=metric.cagr_pct,
            std_dev_annualized=metric.std_dev_annualized,
            sharpe_ratio=metric.sharpe_ratio,
            sortino_ratio=metric.sortino_ratio,
            max_drawdown_pct=metric.max_drawdown_pct,
            health_score=health,
        )
        db.add(snapshot)
    db.commit()
    return metrics, risk, health


def fetch_latest_metrics(
    db: Session,
    scheme: Scheme,
) -> tuple[list[TrailingMetric], RiskSnapshot, float | None]:
    snapshot_rows = list(
        db.execute(
            select(ComputedMetricSnapshot)
            .where(ComputedMetricSnapshot.scheme_id == scheme.id)
            .order_by(ComputedMetricSnapshot.computed_at.desc())
        ).scalars()
    )
    metrics_by_period: dict[str, TrailingMetric] = {}
    for snapshot in snapshot_rows:
        if snapshot.period_label in metrics_by_period:
            continue
        metrics_by_period[snapshot.period_label] = TrailingMetric(
            period_label=snapshot.period_label,
            cagr_pct=float(snapshot.cagr_pct) if snapshot.cagr_pct is not None else None,
            std_dev_annualized=float(snapshot.std_dev_annualized)
            if snapshot.std_dev_annualized is not None
            else None,
            sharpe_ratio=float(snapshot.sharpe_ratio)
            if snapshot.sharpe_ratio is not None
            else None,
            sortino_ratio=float(snapshot.sortino_ratio)
            if snapshot.sortino_ratio is not None
            else None,
            max_drawdown_pct=float(snapshot.max_drawdown_pct)
            if snapshot.max_drawdown_pct is not None
            else None,
        )
    metrics = list(metrics_by_period.values())
    health_score = None
    if snapshot_rows:
        health_score = snapshot_rows[0].health_score
        if health_score is not None:
            health_score = float(health_score)
    reference = next((metric for metric in metrics if metric.period_label == "3Y"), None)
    if reference is None and metrics:
        reference = metrics[0]
    risk = RiskSnapshot(
        std_dev_annualized=reference.std_dev_annualized if reference else None,
        sharpe_ratio=reference.sharpe_ratio if reference else None,
        sortino_ratio=reference.sortino_ratio if reference else None,
        max_drawdown_pct=reference.max_drawdown_pct if reference else None,
    )
    return metrics, risk, health_score
