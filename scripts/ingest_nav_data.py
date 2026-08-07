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
BATCH_CHUNK_SIZE = 6  # smaller than Tigzig's max (50) — a single request for
# all 24 funds' full multi-year history timed out in practice; chunking
# trades a few more requests for each one being fast and reliable
NAV_REQUEST_TIMEOUT = 45
MAX_RETRIES = 2


def load_confirmed_funds() -> list[dict]:
    """Load resolved_schemes.json and use ONLY entries a human has actually
    confirmed — entry["confirmed_scheme_code"] must be manually set to a
    real scheme_code from that entry's candidates (or elsewhere), not left
    null. This is a hard gate, not a suggestion: a comment alone ("human
    picks the right one") didn't stop 7/24 wrong funds from getting
    ingested in Session 6 (e.g. "Quant Tax Plan" auto-matched "Quantum
    ELSS Tax Saver Fund" — text-similarity ranking can't tell two
    different AMCs with similar names apart; only a human checking the
    real fund can).
    """
    raw = json.loads(RESOLVED_SCHEMES_PATH.read_text())
    confirmed = []
    unconfirmed_count = 0
    for entry in raw:
        code = entry.get("confirmed_scheme_code")
        if not code:
            unconfirmed_count += 1
            names = [c.get("scheme_name") for c in entry.get("candidates", [])]
            print(f"  ! SKIPPING (not confirmed): {entry['search_term']!r} — candidates were: {names}")
            continue
        # Find the matching candidate to pull its scheme_name/isin — the
        # confirmed code must actually be one of the returned candidates,
        # not a typo'd/invented one.
        matched = next((c for c in entry["candidates"] if str(c["scheme_code"]) == str(code)), None)
        if matched is None:
            print(f"  ! SKIPPING: confirmed_scheme_code {code!r} for {entry['search_term']!r} "
                  f"doesn't match any of its candidates — check for a typo")
            continue
        confirmed.append(
            {
                "amc_name": entry["amc"],
                "category": entry["category"],
                "scheme_code": str(code),
                "scheme_name": matched["scheme_name"],
                "isin": matched.get("isin"),
            }
        )

    if unconfirmed_count:
        print(f"\n{unconfirmed_count} entries skipped — not yet confirmed. "
              f"Edit {RESOLVED_SCHEMES_PATH.name} and set confirmed_scheme_code for each.\n")
    return confirmed


def _fetch_one_chunk(scheme_codes: list[str]) -> dict:
    """Fetch NAV for a small chunk of scheme codes, retrying on timeout
    before giving up on that chunk. Returns the normalized
    {"schemes": {...}, "not_found": [...]} shape for just this chunk."""
    codes_param = ",".join(scheme_codes)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 2):  # e.g. 1 initial try + 2 retries
        try:
            resp = requests.get(
                TIGZIG_NAV_URL, params={"schemes": codes_param}, timeout=NAV_REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as exc:
            last_error = exc
            print(f"    attempt {attempt} failed for chunk {scheme_codes}: {exc}")
    else:
        print(f"    ! giving up on chunk {scheme_codes} after {MAX_RETRIES + 1} attempts: {last_error}")
        return {"schemes": {}, "not_found": scheme_codes}

    if isinstance(data, dict) and "schemes" in data:
        schemes_raw = data["schemes"]
        not_found = data.get("not_found", [])
    elif isinstance(data, list):
        schemes_raw = data
        not_found = []
    else:
        schemes_raw = [data]
        not_found = []

    if isinstance(schemes_raw, dict):
        schemes_by_code = {str(k): v for k, v in schemes_raw.items()}
    else:  # list of per-scheme objects
        schemes_by_code = {str(item.get("scheme_code")): item for item in schemes_raw}

    return {"schemes": schemes_by_code, "not_found": not_found}


def fetch_batch_nav(scheme_codes: list[str]) -> dict:
    """Fetch NAV history for all scheme_codes, in small chunks rather
    than one big request — fetching full multi-year history for 24 funds
    in a single call timed out in practice against the free Tigzig API.
    Merges all chunks into one {"schemes": {...}, "not_found": [...]}
    result so the caller doesn't need to know chunking happened.
    """
    all_schemes: dict = {}
    all_not_found: list = []

    for i in range(0, len(scheme_codes), BATCH_CHUNK_SIZE):
        chunk = scheme_codes[i : i + BATCH_CHUNK_SIZE]
        print(f"  fetching chunk {i // BATCH_CHUNK_SIZE + 1}: {chunk}")
        result = _fetch_one_chunk(chunk)
        all_schemes.update(result["schemes"])
        all_not_found.extend(result["not_found"])

    return {"schemes": all_schemes, "not_found": all_not_found}


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