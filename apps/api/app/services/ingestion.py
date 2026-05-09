from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
import re

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AMC, NAVHistoryDaily, Scheme
from app.services.mfapi_client import MFAPIClient, NavAllEntry, SchemeDetail, SchemeListEntry

UNKNOWN_AMC_CODE = "UNKNOWN"
UNKNOWN_AMC_NAME = "Unknown AMC"


@dataclass(frozen=True)
class SyncResult:
    schemes_added: int
    schemes_updated: int
    nav_rows_added: int


def ensure_unknown_amc(db: Session) -> AMC:
    existing = db.execute(select(AMC).where(AMC.amfi_code == UNKNOWN_AMC_CODE)).scalar_one_or_none()
    if existing:
        return existing
    amc = AMC(amfi_code=UNKNOWN_AMC_CODE, name=UNKNOWN_AMC_NAME, short_name="Unknown")
    db.add(amc)
    db.commit()
    db.refresh(amc)
    return amc


def sync_mf_universe(db: Session, client: MFAPIClient | None = None) -> SyncResult:
    if not settings.auto_sync_mf_universe:
        return SyncResult(schemes_added=0, schemes_updated=0, nav_rows_added=0)

    local_client = client or MFAPIClient()
    try:
        scheme_list = local_client.fetch_scheme_list()
        nav_entries = local_client.fetch_nav_all() if settings.auto_sync_navs else []
    finally:
        if client is None:
            local_client.close()

    unknown_amc = ensure_unknown_amc(db)
    nav_map = {entry.scheme_code: entry for entry in nav_entries}

    codes = {entry.scheme_code for entry in scheme_list}.union(nav_map.keys())
    existing = {
        scheme.amfi_scheme_code: scheme
        for scheme in db.execute(select(Scheme).where(Scheme.amfi_scheme_code.in_(codes))).scalars()
    }

    schemes_added = 0
    schemes_updated = 0
    new_schemes: list[Scheme] = []

    for entry in _merge_scheme_sources(scheme_list, nav_entries):
        scheme = existing.get(entry.scheme_code)
        plan, option = parse_plan_option(entry.scheme_name)
        if scheme is None:
            new_scheme = Scheme(
                amfi_scheme_code=entry.scheme_code,
                amc_id=unknown_amc.id,
                scheme_name=entry.scheme_name,
                plan=plan,
                option=option,
            )
            new_schemes.append(new_scheme)
            schemes_added += 1
        else:
            updated = False
            if scheme.scheme_name != entry.scheme_name:
                scheme.scheme_name = entry.scheme_name
                updated = True
            if plan and scheme.plan != plan:
                scheme.plan = plan
                updated = True
            if option and scheme.option != option:
                scheme.option = option
                updated = True
            if updated:
                schemes_updated += 1

    if new_schemes:
        db.add_all(new_schemes)
    db.commit()

    nav_rows_added = 0
    if nav_entries:
        scheme_ids = {
            scheme.amfi_scheme_code: scheme.id
            for scheme in db.execute(select(Scheme).where(Scheme.amfi_scheme_code.in_(nav_map.keys()))).scalars()
        }
        nav_rows_added = _upsert_nav_entries(db, nav_entries, scheme_ids)

    return SyncResult(
        schemes_added=schemes_added,
        schemes_updated=schemes_updated,
        nav_rows_added=nav_rows_added,
    )


def update_scheme_from_detail(db: Session, scheme: Scheme, detail: SchemeDetail) -> None:
    if detail.scheme_name:
        scheme.scheme_name = detail.scheme_name
    if detail.fund_house:
        amc_code = slugify(detail.fund_house)
        amc = db.execute(select(AMC).where(AMC.amfi_code == amc_code)).scalar_one_or_none()
        if amc is None:
            amc = AMC(amfi_code=amc_code, name=detail.fund_house, short_name=_short_name(detail.fund_house))
            db.add(amc)
            db.flush()
        scheme.amc_id = amc.id
    if detail.scheme_category:
        scheme.sebi_category = detail.scheme_category
    if detail.scheme_type and not scheme.sebi_sub_category:
        scheme.sebi_sub_category = detail.scheme_type


def store_nav_history(
    db: Session,
    scheme_id: int,
    history: Iterable[tuple[date, float]],
) -> int:
    rows = [
        {"scheme_id": scheme_id, "nav_date": nav_date, "nav": Decimal(str(nav))}
        for nav_date, nav in history
    ]
    if not rows:
        return 0
    return _insert_nav_rows(db, rows)


def parse_plan_option(name: str) -> tuple[str | None, str | None]:
    plan = None
    option = None
    lower = name.lower()
    if "direct" in lower:
        plan = "Direct"
    elif "regular" in lower:
        plan = "Regular"
    if "growth" in lower:
        option = "Growth"
    elif "idcw" in lower or "dividend" in lower:
        option = "IDCW"
    return plan, option


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned[:20] or UNKNOWN_AMC_CODE.lower()


def _short_name(name: str) -> str:
    tokens = [t for t in re.split(r"\s+", name.strip()) if t]
    return tokens[0][:10] if tokens else "AMC"


def _merge_scheme_sources(
    scheme_list: list[SchemeListEntry],
    nav_entries: list[NavAllEntry],
) -> list[SchemeListEntry]:
    merged: dict[str, SchemeListEntry] = {entry.scheme_code: entry for entry in scheme_list}
    for nav_entry in nav_entries:
        merged.setdefault(
            nav_entry.scheme_code,
            SchemeListEntry(scheme_code=nav_entry.scheme_code, scheme_name=nav_entry.scheme_name),
        )
    return list(merged.values())


def _insert_nav_rows(db: Session, rows: list[dict]) -> int:
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = insert(NAVHistoryDaily).values(rows).on_conflict_do_nothing(
            index_elements=["scheme_id", "nav_date"]
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0

    inserted = 0
    for row in rows:
        exists = db.execute(
            select(NAVHistoryDaily).where(
                NAVHistoryDaily.scheme_id == row["scheme_id"],
                NAVHistoryDaily.nav_date == row["nav_date"],
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(NAVHistoryDaily(**row))
            inserted += 1
    db.commit()
    return inserted


def _upsert_nav_entries(
    db: Session, nav_entries: list[NavAllEntry], scheme_ids: dict[str, int]
) -> int:
    rows = []
    for entry in nav_entries:
        scheme_id = scheme_ids.get(entry.scheme_code)
        if scheme_id is None:
            continue
        rows.append(
            {
                "scheme_id": scheme_id,
                "nav_date": entry.nav_date,
                "nav": Decimal(str(entry.nav)),
            }
        )
    return _insert_nav_rows(db, rows)


def encode_metadata(metadata: dict) -> str:
    return json.dumps(metadata, ensure_ascii=False, sort_keys=True)
