"""Metric computation tasks for FundLens worker."""

import structlog

from app.celery_app import celery_app

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

    try:
        # TODO Phase 2: implement actual metric computation
        # from analytics_engine.calculators import cagr, max_drawdown, sharpe
        # schemes = fetch_active_schemes(db)
        # for scheme in schemes:
        #     navs = fetch_nav_history(db, scheme.id)
        #     metrics = compute_all_metrics(navs)
        #     save_computed_metrics(db, scheme.id, metrics)

        logger.info("recompute_trailing_metrics_daily_completed", status="stub")
        return {"status": "ok", "schemes_processed": 0, "note": "stub — Phase 2 implementation pending"}

    except Exception as exc:
        logger.error("recompute_trailing_metrics_daily_failed", error=str(exc))
        raise self.retry(exc=exc)
