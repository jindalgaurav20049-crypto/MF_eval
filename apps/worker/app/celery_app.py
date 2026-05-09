"""Celery application bootstrap for FundLens worker."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "fundlens_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.metrics", "app.tasks.ingestion"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "sync-mf-universe-daily": {
        "task": "app.tasks.ingestion.sync_mf_universe",
        "schedule": crontab(hour=0, minute=30),
    },
    "recompute-trailing-metrics-daily": {
        "task": "app.tasks.metrics.recompute_trailing_metrics_daily",
        "schedule": crontab(hour=1, minute=30),  # 1:30 AM IST daily
    },
    "watchlist-alerts-hourly": {
        "task": "app.tasks.metrics.generate_watchlist_alerts",
        "schedule": crontab(minute=0, hour="*/1"),
    },
}
