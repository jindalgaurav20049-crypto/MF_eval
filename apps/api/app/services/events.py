from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FundManagerTenure, Scheme, SchemeEvent


def import_manager_changes(db: Session, file_bytes: bytes) -> int:
    reader = csv.DictReader(io.StringIO(file_bytes.decode("utf-8", errors="ignore")))
    count = 0
    for row in reader:
        scheme = _resolve_scheme(db, row.get("scheme_code") or row.get("scheme_id"))
        if scheme is None:
            continue
        db.add(
            FundManagerTenure(
                scheme_id=scheme.id,
                manager_name=str(row.get("manager_name") or row.get("manager") or "").strip(),
                start_date=_parse_date(row.get("start_date")) or date.today(),
                end_date=_parse_date(row.get("end_date")),
                is_current=_parse_bool(row.get("is_current")),
            )
        )
        count += 1
    db.commit()
    return count


def import_scheme_events(db: Session, file_bytes: bytes) -> int:
    reader = csv.DictReader(io.StringIO(file_bytes.decode("utf-8", errors="ignore")))
    count = 0
    for row in reader:
        scheme = _resolve_scheme(db, row.get("scheme_code") or row.get("scheme_id"))
        if scheme is None:
            continue
        metadata = row.get("metadata_json") or row.get("metadata")
        metadata_json = None
        if metadata:
            try:
                metadata_json = json.dumps(json.loads(metadata))
            except json.JSONDecodeError:
                metadata_json = json.dumps({"raw": metadata})
        db.add(
            SchemeEvent(
                scheme_id=scheme.id,
                event_date=_parse_date(row.get("event_date")) or date.today(),
                event_type=str(row.get("event_type") or "sebi_directive"),
                description=str(row.get("description") or "").strip() or None,
                metadata_json=metadata_json,
            )
        )
        count += 1
    db.commit()
    return count


def list_manager_changes(db: Session, scheme_id: int) -> list[FundManagerTenure]:
    return (
        db.execute(
            select(FundManagerTenure)
            .where(FundManagerTenure.scheme_id == scheme_id)
            .order_by(FundManagerTenure.start_date.desc())
        )
        .scalars()
        .all()
    )


def list_scheme_events(db: Session, scheme_id: int) -> list[SchemeEvent]:
    return (
        db.execute(
            select(SchemeEvent)
            .where(SchemeEvent.scheme_id == scheme_id)
            .order_by(SchemeEvent.event_date.desc())
        )
        .scalars()
        .all()
    )


def _resolve_scheme(db: Session, scheme_code: Any) -> Scheme | None:
    if not scheme_code:
        return None
    return db.execute(
        select(Scheme).where(Scheme.amfi_scheme_code == str(scheme_code).strip())
    ).scalar_one_or_none()


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "n"}:
        return False
    return True
