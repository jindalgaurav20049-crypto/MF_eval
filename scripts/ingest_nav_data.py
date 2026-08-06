"""
Ingest real NAV data — Phase A, step 2.

Reads the human-reviewed scheme codes from scripts/resolved_schemes.json
(produced by lookup_schemes.py) and populates the database:
  1. amc        — one row per fund house (AMC), get-or-create by name
  2. scheme     — one row per fund, get-or-create by AMFI scheme code
  3. nav_history_daily — full price history per fund, via Tigzig's batch
                  NAV endpoint (up to 50 scheme codes in a single call)

This is independent, from-scratch work — NOT copied from PR #2
(copilot/implement-phase-2-application). See learning.md Session 4 for
why: Gaurav's call was to use that branch as a design reference only.

Usage:
    # Postgres must be running (see docker-compose.yml) and DATABASE_URL
    # configured (defaults to the value in apps/api/app/config.py).
    pip install requests sqlalchemy psycopg2-binary
    python scripts/ingest_nav_data.py

What this does NOT do (by design, for now):
  - Does not compute CAGR/Sharpe/Drawdown — that's the worker's job
    (apps/worker/app/tasks/metrics.py), using packages/analytics-engine.
    Ingestion's only responsibility is getting correct raw data into the
    database. Keeping these separate means a bug in one doesn't hide in
    the other.
  - Does not silently insert NAV = 0 rows. See handle_zero_nav() —
    the edge case flagged back in Session 2 (defunct/segregated schemes
    legitimately report a zero NAV; treating that as a real price would
    silently corrupt CAGR/Sharpe/Drawdown for that fund).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

# apps/api's "app" package isn't installed — add it to sys.path so this
# standalone script can reuse the real SQLAlchemy models rather than
# redefining them (redefining would risk the schema drifting out of sync).
API_APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_APP_ROOT))

from app.db.base import SessionLocal  # noqa: E402
from app.db.models import AMC, NAVHistoryDaily, Scheme  # noqa: E402

RESOLVED_SCHEMES_PATH = Path(__file__).parent / "resolved_schemes.json"
TIGZIG_NAV_URL = "https://api.tigzig.com/mf/v1/nav"
BATCH_SIZE = 50  # Tigzig's documented max identifiers per /nav call


def load_confirmed_funds() -> list[dict]:
    """Load resolved_schemes.json and take the top-ranked candidate per
    fund as the confirmed pick. lookup_schemes.py already sorted
    candidates by match score and a human reviewed the 24/24 clean
    resolution in Session 4 — if you haven't actually eyeballed
    resolved_schemes.json yourself yet, do that before trusting this."""
    raw = json.loads(RESOLVED_SCHEMES_PATH.read_text())
    confirmed = []
    for entry in raw:
        if not entry["candidates"]:
            print(f"  ! skipping {entry['search_term']!r} — no candidates to pick from")
            continue
        top = entry["candidates"][0]
        confirmed.append(
            {
                "amc_name": entry["amc"],
                "category": entry["category"],
                "scheme_code": str(top["scheme_code"]),
                "scheme_name": top["scheme_name"],
                "isin": top.get("isin"),
            }
        )
    return confirmed


def fetch_batch_nav(scheme_codes: list[str]) -> dict:
    """Call Tigzig's batch NAV endpoint and normalize the response into
    {"schemes": {scheme_code_str: payload_dict}, "not_found": [...]}
    regardless of the exact shape Tigzig returns.

    Confirmed by a real run: the top-level response has a "schemes" key,
    but its value is a LIST of per-scheme objects (each containing its
    own scheme_code field), not a dict keyed by code as first assumed.
    This function now handles both shapes so it doesn't break again if
    Tigzig's exact format shifts slightly.
    """
    codes_param = ",".join(scheme_codes)
    resp = requests.get(TIGZIG_NAV_URL, params={"schemes": codes_param}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and "schemes" in data:
        schemes_raw = data["schemes"]
        not_found = data.get("not_found", [])
    elif isinstance(data, list):
        schemes_raw = data
        not_found = []
    else:
        # Single-scheme-shaped response, even though we asked for a batch
        schemes_raw = [data]
        not_found = []

    if isinstance(schemes_raw, dict):
        schemes_by_code = {str(k): v for k, v in schemes_raw.items()}
    else:  # list of per-scheme objects
        schemes_by_code = {str(item.get("scheme_code")): item for item in schemes_raw}

    return {"schemes": schemes_by_code, "not_found": not_found}


def is_zero_or_invalid_nav(raw_nav) -> bool:
    """Flags NAV rows we should NOT insert as real prices.

    This is the edge case from Session 2: some schemes legitimately report
    NAV = 0 because they're defunct/frozen "segregated portfolios" (e.g.
    old debt-fund carve-outs tied to a specific defaulted bond). Inserting
    those as real prices would silently corrupt CAGR/Sharpe/Drawdown for
    that fund — a fund that "returned -100%" every day is not the same
    data quality problem as a fund that simply has no NAV row for a date.
    """
    try:
        value = Decimal(str(raw_nav))
    except (InvalidOperation, TypeError):
        return True  # unparseable — treat as invalid, don't insert
    return value <= 0


def upsert_amc(session, amc_name: str) -> AMC:
    existing = session.query(AMC).filter_by(name=amc_name).one_or_none()
    if existing:
        return existing
    # amfi_code is required and unique but Tigzig doesn't give us AMFI's
    # own AMC code — use a slug of the name as a stand-in until a real
    # AMC code source is wired up. Flagging this rather than hiding it.
    amfi_code_stub = amc_name.lower().replace(" ", "-")[:20]
    amc = AMC(amfi_code=amfi_code_stub, name=amc_name)
    session.add(amc)
    session.flush()  # get amc.id without a full commit
    return amc


def upsert_scheme(session, amc: AMC, fund: dict) -> Scheme:
    existing = session.query(Scheme).filter_by(amfi_scheme_code=fund["scheme_code"]).one_or_none()
    if existing:
        return existing
    scheme = Scheme(
        amfi_scheme_code=fund["scheme_code"],
        amc_id=amc.id,
        scheme_name=fund["scheme_name"],
        sebi_category=fund["category"],
        plan="Direct",
    )
    session.add(scheme)
    session.flush()
    return scheme


def insert_nav_rows(session, scheme: Scheme, nav_data: list[dict]) -> tuple[int, int]:
    """Insert NAV history rows for one scheme. Returns (inserted, skipped)."""
    existing_dates = {
        row.nav_date
        for row in session.query(NAVHistoryDaily.nav_date).filter_by(scheme_id=scheme.id)
    }

    inserted = skipped = 0
    for point in nav_data:
        nav_date = datetime.strptime(point["date"], "%Y-%m-%d").date() if "-" in point["date"] else date.fromisoformat(point["date"])
        if nav_date in existing_dates:
            continue  # already ingested — safe to re-run this script
        if is_zero_or_invalid_nav(point.get("nav")):
            skipped += 1
            continue
        session.add(NAVHistoryDaily(scheme_id=scheme.id, nav_date=nav_date, nav=Decimal(str(point["nav"]))))
        inserted += 1
    return inserted, skipped


def main() -> None:
    funds = load_confirmed_funds()
    print(f"Loaded {len(funds)} confirmed funds from {RESOLVED_SCHEMES_PATH.name}")

    scheme_codes = [f["scheme_code"] for f in funds]
    print(f"Fetching batch NAV history for {len(scheme_codes)} schemes from Tigzig...")
    batch = fetch_batch_nav(scheme_codes)

    if batch.get("not_found"):
        print(f"  ! Tigzig could not find: {batch['not_found']}")

    session = SessionLocal()
    total_inserted = total_skipped = 0
    try:
        for fund in funds:
            code = fund["scheme_code"]
            scheme_payload = batch["schemes"].get(code)
            if scheme_payload is None:
                print(f"  ! no NAV data returned for {fund['scheme_name']} ({code}) — skipping")
                continue

            amc = upsert_amc(session, fund["amc_name"])
            scheme = upsert_scheme(session, amc, fund)
            inserted, skipped = insert_nav_rows(session, scheme, scheme_payload.get("data", []))
            total_inserted += inserted
            total_skipped += skipped
            print(f"  {fund['scheme_name']}: +{inserted} rows ({skipped} zero/invalid NAV rows skipped)")

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"\nDone. {total_inserted} NAV rows inserted, {total_skipped} zero/invalid rows skipped.")


if __name__ == "__main__":
    main()