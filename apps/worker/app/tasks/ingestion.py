from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx
import structlog
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.db import SessionLocal
from app.models import NAVHistoryDaily, Scheme

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.ingestion.sync_mf_universe")
def sync_mf_universe() -> dict:
    db = SessionLocal()
    try:
        nav_entries = _fetch_nav_all()
        _insert_navs(db, nav_entries)
        return {"status": "ok", "nav_rows": len(nav_entries)}
    finally:
        db.close()


def _fetch_nav_all() -> list[dict]:
    response = httpx.get(settings.amfi_nav_url, timeout=settings.mfapi_timeout_seconds)
    response.raise_for_status()
    entries: list[dict] = []
    for line in response.text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith(("Scheme Code", "Total", "Mutual Fund")):
            continue
        parts = [p.strip() for p in cleaned.split(";")]
        if len(parts) < 6:
            continue
        scheme_code = parts[0]
        nav = _safe_float(parts[4])
        nav_date = _parse_date(parts[5])
        if scheme_code and nav is not None and nav_date:
            entries.append({"scheme_code": scheme_code, "nav": nav, "nav_date": nav_date})
    return entries


def _insert_navs(db: Session, entries: list[dict]) -> None:
    if not entries:
        return
    scheme_ids = {
        scheme.amfi_scheme_code: scheme.id
        for scheme in db.execute(
            select(Scheme).where(
                Scheme.amfi_scheme_code.in_([e["scheme_code"] for e in entries])
            )
        ).scalars()
    }
    rows = []
    for entry in entries:
        scheme_id = scheme_ids.get(entry["scheme_code"])
        if scheme_id is None:
            continue
        rows.append(
            {
                "scheme_id": scheme_id,
                "nav_date": entry["nav_date"],
                "nav": Decimal(str(entry["nav"])),
            }
        )
    if not rows:
        return
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = insert(NAVHistoryDaily).values(rows).on_conflict_do_nothing(
            index_elements=["scheme_id", "nav_date"]
        )
        db.execute(stmt)
        db.commit()
        return
    for row in rows:
        exists = db.execute(
            select(NAVHistoryDaily).where(
                NAVHistoryDaily.scheme_id == row["scheme_id"],
                NAVHistoryDaily.nav_date == row["nav_date"],
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(NAVHistoryDaily(**row))
    db.commit()


def _parse_date(value: str) -> datetime.date | None:
    if not value:
        return None
    text = value.strip()
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
