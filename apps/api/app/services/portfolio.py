from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    NAVHistoryDaily,
    Scheme,
    SchemePortfolioSnapshot,
    UserPortfolioTxn,
)


@dataclass(frozen=True)
class PortfolioImportResult:
    user_id: str
    transactions_loaded: int
    schemes_updated: int


def import_holdings_snapshot(db: Session, file_bytes: bytes) -> int:
    reader = csv.DictReader(io.StringIO(file_bytes.decode("utf-8", errors="ignore")))
    count = 0
    for row in reader:
        scheme = _resolve_scheme(db, row.get("scheme_code") or row.get("scheme_id"))
        if scheme is None:
            continue
        snapshot_date = _parse_date(row.get("snapshot_date")) or date.today()
        db.add(
            SchemePortfolioSnapshot(
                scheme_id=scheme.id,
                snapshot_date=snapshot_date,
                isin=_clean(row.get("isin")),
                instrument_name=_clean(row.get("instrument_name")),
                instrument_type=_clean(row.get("instrument_type")),
                sector=_clean(row.get("sector")),
                weight_pct=_parse_decimal(row.get("weight_pct")),
                market_value_cr=_parse_decimal(row.get("market_value_cr")),
                rating=_clean(row.get("rating")),
            )
        )
        count += 1
    db.commit()
    return count


def import_portfolio_transactions(
    db: Session,
    user_email: str,
    file_name: str,
    file_bytes: bytes,
) -> PortfolioImportResult:
    user = _get_or_create_user(db, user_email)
    transactions = _parse_transactions(file_name, file_bytes)
    schemes_updated = 0
    for txn in transactions:
        scheme = _resolve_scheme(db, txn.scheme_code, txn.scheme_name)
        if scheme is None:
            continue
        schemes_updated += 1
        db.add(
            UserPortfolioTxn(
                user_id=user.id,
                scheme_id=scheme.id,
                txn_date=txn.txn_date,
                txn_type=txn.txn_type,
                amount=txn.amount,
                units=txn.units,
                nav_at_txn=txn.nav_at_txn,
            )
        )
    db.commit()
    return PortfolioImportResult(
        user_id=str(user.id),
        transactions_loaded=len(transactions),
        schemes_updated=schemes_updated,
    )


def compute_portfolio_overlap(db: Session, user_id: str) -> list[dict]:
    user_key = _normalize_user_id(user_id)
    scheme_ids = [
        row[0]
        for row in db.execute(
            select(UserPortfolioTxn.scheme_id)
            .where(UserPortfolioTxn.user_id == user_key)
            .distinct()
        )
    ]
    if not scheme_ids:
        return []
    snapshots = db.execute(
        select(SchemePortfolioSnapshot)
        .where(SchemePortfolioSnapshot.scheme_id.in_(scheme_ids))
        .order_by(SchemePortfolioSnapshot.snapshot_date.desc())
    ).scalars()
    holdings: dict[str, dict] = {}
    for snapshot in snapshots:
        key = snapshot.isin or snapshot.instrument_name or ""
        if not key:
            continue
        entry = holdings.setdefault(
            key,
            {
                "instrument": snapshot.instrument_name,
                "isin": snapshot.isin,
                "funds": set(),
                "weight": 0.0,
            },
        )
        entry["funds"].add(snapshot.scheme_id)
        entry["weight"] += float(snapshot.weight_pct or 0)
    overlap = [
        {
            "instrument": entry["instrument"],
            "isin": entry["isin"],
            "fund_count": len(entry["funds"]),
            "weight_pct_sum": round(entry["weight"], 2),
        }
        for entry in holdings.values()
        if len(entry["funds"]) > 1
    ]
    overlap.sort(key=lambda row: row["fund_count"], reverse=True)
    return overlap[:50]


def compute_tax_scenarios(db: Session, user_id: str) -> list[dict]:
    user_key = _normalize_user_id(user_id)
    transactions = db.execute(
        select(UserPortfolioTxn).where(UserPortfolioTxn.user_id == user_key)
    ).scalars()
    results: list[dict] = []
    for txn in transactions:
        latest_nav = _latest_nav(db, txn.scheme_id)
        if latest_nav is None:
            continue
        holding_period_days = (date.today() - txn.txn_date).days
        gain = (Decimal(str(latest_nav)) - (txn.nav_at_txn or Decimal("0"))) * (
            txn.units or Decimal("0")
        )
        tax_rate = Decimal("0.10") if holding_period_days >= 365 else Decimal("0.15")
        results.append(
            {
                "scheme_id": txn.scheme_id,
                "txn_date": txn.txn_date.isoformat(),
                "holding_days": holding_period_days,
                "estimated_gain": float(gain),
                "estimated_tax": float(gain * tax_rate),
            }
        )
    return results


@dataclass(frozen=True)
class ParsedTransaction:
    scheme_code: str | None
    scheme_name: str | None
    txn_date: date
    txn_type: str
    amount: Decimal | None
    units: Decimal | None
    nav_at_txn: Decimal | None


def _parse_transactions(file_name: str, file_bytes: bytes) -> list[ParsedTransaction]:
    name_lower = file_name.lower()
    if name_lower.endswith(".csv"):
        return _parse_csv(file_bytes)
    if name_lower.endswith(".json"):
        return _parse_json(file_bytes)
    if name_lower.endswith(".pdf"):
        return _parse_pdf(file_bytes)
    return _parse_text(file_bytes)


def _parse_csv(file_bytes: bytes) -> list[ParsedTransaction]:
    stream = io.StringIO(file_bytes.decode("utf-8", errors="ignore"))
    reader = csv.DictReader(stream)
    records: list[ParsedTransaction] = []
    for row in reader:
        records.append(_parse_row(row))
    return records


def _parse_json(file_bytes: bytes) -> list[ParsedTransaction]:
    payload = json.loads(file_bytes.decode("utf-8", errors="ignore"))
    records: list[ParsedTransaction] = []
    for row in payload:
        records.append(_parse_row(row))
    return records


def _parse_text(file_bytes: bytes) -> list[ParsedTransaction]:
    text = file_bytes.decode("utf-8", errors="ignore")
    records: list[ParsedTransaction] = []
    for line in text.splitlines():
        if "," not in line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        row = {
            "scheme_code": parts[0],
            "scheme_name": parts[1],
            "txn_date": parts[2],
            "txn_type": parts[3],
            "amount": parts[4] if len(parts) > 4 else None,
            "units": parts[5] if len(parts) > 5 else None,
            "nav": parts[6] if len(parts) > 6 else None,
        }
        records.append(_parse_row(row))
    return records


def _parse_pdf(file_bytes: bytes) -> list[ParsedTransaction]:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return _parse_text(text.encode("utf-8"))


def _parse_row(row: dict[str, Any]) -> ParsedTransaction:
    return ParsedTransaction(
        scheme_code=_clean(row.get("scheme_code") or row.get("schemeCode") or row.get("scheme_id")),
        scheme_name=_clean(row.get("scheme_name") or row.get("schemeName")),
        txn_date=_parse_date(row.get("txn_date") or row.get("date") or row.get("transaction_date")),
        txn_type=str(row.get("txn_type") or row.get("transaction_type") or "purchase").lower(),
        amount=_parse_decimal(row.get("amount")),
        units=_parse_decimal(row.get("units")),
        nav_at_txn=_parse_decimal(row.get("nav") or row.get("nav_at_txn")),
    )


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = _clean(value)
    if not text:
        return date.today()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.today()


def _parse_decimal(value: Any) -> Decimal | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_scheme(db: Session, scheme_code: str | None, scheme_name: str | None) -> Scheme | None:
    if scheme_code:
        scheme = db.execute(
            select(Scheme).where(Scheme.amfi_scheme_code == scheme_code)
        ).scalar_one_or_none()
        if scheme:
            return scheme
    if scheme_name:
        return db.execute(
            select(Scheme).where(Scheme.scheme_name.ilike(f"%{scheme_name}%"))
        ).scalar_one_or_none()
    return None


def _get_or_create_user(db: Session, email: str) -> AppUser:
    user = db.execute(select(AppUser).where(AppUser.email == email)).scalar_one_or_none()
    if user:
        return user
    user = AppUser(email=email, display_name=email.split("@")[0])
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _latest_nav(db: Session, scheme_id: int) -> float | None:
    nav = db.execute(
        select(NAVHistoryDaily.nav)
        .where(NAVHistoryDaily.scheme_id == scheme_id)
        .order_by(NAVHistoryDaily.nav_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(nav) if nav is not None else None


def _normalize_user_id(user_id: str) -> uuid.UUID | str:
    try:
        return uuid.UUID(user_id)
    except (ValueError, TypeError):
        return user_id
