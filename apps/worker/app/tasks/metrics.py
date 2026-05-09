"""Metric computation tasks for FundLens worker."""

from datetime import date, datetime, timezone
import math
import statistics

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.db import SessionLocal
from app.models import ComputedMetricSnapshot, NAVHistoryDaily, Scheme, UserNotification, UserWatchlist
from analytics_engine.calculators.cagr import cagr_from_nav_series
from analytics_engine.calculators.drawdown import max_drawdown
from analytics_engine.calculators.sharpe import sharpe_ratio

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.tasks.metrics.recompute_trailing_metrics_daily",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def recompute_trailing_metrics_daily(self) -> dict:
    """
    Placeholder task: recompute trailing return metrics for all active schemes.

    Phase 2 implementation will:
    1. Fetch all active schemes from the database
    2. Load NAV history from nav_history_daily
    3. Call analytics-engine to compute CAGR, Sharpe, Drawdown, etc.
    4. Write results to computed_metric_snapshot
    5. Invalidate Redis cache for affected schemes
    """
    logger.info("recompute_trailing_metrics_daily_started")

    db = SessionLocal()
    try:
        schemes = db.execute(select(Scheme)).scalars().all()
        processed = 0
        for scheme in schemes:
            nav_rows = (
                db.execute(
                    select(NAVHistoryDaily)
                    .where(NAVHistoryDaily.scheme_id == scheme.id)
                    .order_by(NAVHistoryDaily.nav_date.asc())
                )
                .scalars()
                .all()
            )
            if len(nav_rows) < 2:
                continue
            nav_series = [(row.nav_date, float(row.nav)) for row in nav_rows]
            metrics = _compute_trailing_metrics(nav_series)
            computed_at = datetime.now(timezone.utc)
            for metric in metrics:
                snapshot = ComputedMetricSnapshot(
                    scheme_id=scheme.id,
                    computed_at=computed_at,
                    period_label=metric["period_label"],
                    cagr_pct=metric["cagr_pct"],
                    std_dev_annualized=metric["std_dev_annualized"],
                    sharpe_ratio=metric["sharpe_ratio"],
                    sortino_ratio=metric["sortino_ratio"],
                    max_drawdown_pct=metric["max_drawdown_pct"],
                    health_score=metric["health_score"],
                )
                db.add(snapshot)
            processed += 1
        db.commit()
        logger.info("recompute_trailing_metrics_daily_completed", schemes_processed=processed)
        return {"status": "ok", "schemes_processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("recompute_trailing_metrics_daily_failed", error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.tasks.metrics.generate_watchlist_alerts")
def generate_watchlist_alerts() -> dict:
    db = SessionLocal()
    try:
        watchlist = db.execute(select(UserWatchlist)).scalars().all()
        alerts = 0
        for entry in watchlist:
            snapshot = (
                db.execute(
                    select(ComputedMetricSnapshot)
                    .where(ComputedMetricSnapshot.scheme_id == entry.scheme_id)
                    .order_by(ComputedMetricSnapshot.computed_at.desc())
                )
                .scalars()
                .first()
            )
            if snapshot is None or snapshot.health_score is None:
                continue
            if float(snapshot.health_score) < settings.health_alert_threshold:
                scheme = (
                    db.execute(select(Scheme).where(Scheme.id == entry.scheme_id))
                    .scalars()
                    .first()
                )
                scheme_name = scheme.scheme_name if scheme else "this fund"
                notification = UserNotification(
                    user_id=entry.user_id,
                    scheme_id=entry.scheme_id,
                    notification_type="health_drop",
                    title="Fund health dropped",
                    message=f"Fund {scheme_name} health score dipped below 50.",
                    status="queued",
                )
                db.add(notification)
                alerts += 1
        db.commit()
        return {"status": "ok", "alerts": alerts}
    finally:
        db.close()


def _compute_trailing_metrics(nav_series: list[tuple[date, float]]) -> list[dict]:
    if len(nav_series) < 2:
        return []
    latest_date = nav_series[-1][0]
    periods = {"1Y": 365, "3Y": 365 * 3, "5Y": 365 * 5}
    results: list[dict] = []
    for label, days in periods.items():
        sliced = [row for row in nav_series if (latest_date - row[0]).days <= days]
        if len(sliced) < 2:
            continue
        navs = [row[1] for row in sliced]
        years = max((sliced[-1][0] - sliced[0][0]).days / 365.25, 0.01)
        try:
            cagr_pct = cagr_from_nav_series(navs, years=years) * 100
        except ValueError:
            cagr_pct = 0.0
        returns = _returns_from_navs(navs)
        std_dev = _annualized_std_dev(returns, 252)
        monthly_returns = _monthly_returns(sliced)
        sharpe_value = sharpe_ratio(monthly_returns) if monthly_returns else None
        sortino_value = _sortino_ratio(monthly_returns)
        try:
            drawdown_pct = max_drawdown(navs) * 100
        except ValueError:
            drawdown_pct = 0.0
        health_score = _compute_health_score(cagr_pct, drawdown_pct, sharpe_value)
        results.append(
            {
                "period_label": label,
                "cagr_pct": round(cagr_pct, 2),
                "std_dev_annualized": std_dev,
                "sharpe_ratio": sharpe_value,
                "sortino_ratio": sortino_value,
                "max_drawdown_pct": round(drawdown_pct, 2),
                "health_score": health_score,
            }
        )
    return results


def _returns_from_navs(navs: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(navs, navs[1:]):
        if previous <= 0:
            continue
        returns.append((current / previous) - 1)
    return returns


def _annualized_std_dev(returns: list[float], periods_per_year: int) -> float | None:
    if len(returns) < 2:
        return None
    try:
        return round(statistics.stdev(returns) * math.sqrt(periods_per_year) * 100, 2)
    except statistics.StatisticsError:
        return None


def _monthly_returns(nav_series: list[tuple[date, float]]) -> list[float]:
    monthly: dict[tuple[int, int], float] = {}
    for nav_date, nav in nav_series:
        monthly[(nav_date.year, nav_date.month)] = nav
    ordered = [monthly[key] for key in sorted(monthly)]
    return _returns_from_navs(ordered)


def _sortino_ratio(returns: list[float], target_return: float = 0.0) -> float | None:
    if len(returns) < 6:
        return None
    downside = [r - target_return for r in returns if r < target_return]
    if not downside:
        return None
    downside_std = statistics.pstdev(downside)
    if downside_std == 0:
        return None
    mean_return = statistics.mean(returns)
    return round((mean_return - target_return) / downside_std, 2)


def _compute_health_score(cagr_pct: float, drawdown_pct: float, sharpe_value: float | None) -> float:
    """Score health on a 0-80 scale using returns, drawdown, and Sharpe.

    The score caps returns between -10% and 30% (max 30 pts), drawdowns reward
    lower absolute drawdown up to 30 pts, and Sharpe contributes up to 20 pts.
    These weights bias toward consistent long-term returns with controlled drawdown.
    """
    return_score = min(max(cagr_pct, -10), 30)
    drawdown_score = max(0.0, 30 - abs(drawdown_pct))
    sharpe_score = min(max((sharpe_value or 0) * 20, 0), 20)
    return round(return_score + drawdown_score + sharpe_score, 2)
