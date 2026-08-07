# FundLens — Learning Log

Session-by-session notes: what we did, what concepts came up, and interview
questions/answers worth being able to explain out loud. Kept beginner-friendly
in explanation, but not in substance — the goal is to actually understand
these well enough to defend them in an interview, not just recognize the terms.

---

## Session 1 — Repo Review & Planning

**Date:** 2026-07-26

### What we did
- Cloned and reviewed the full existing scaffold: `apps/api`, `apps/worker`,
  `apps/mobile`, `packages/analytics-engine`.
- Established the real state of the project: the math library and DB schema
  are solid and complete; the API is stub data; the worker is an empty
  function with a plan in comments; the mobile app is partially wired to the
  (stub) API.
- Set direction: goal is to make this a genuinely resume/interview-ready
  project — real data, correct edge-case handling, tests, deployment — not
  just more features.

### Concepts introduced this session

**CAGR (Compound Annual Growth Rate)**
- What: the *smoothed* yearly growth rate that would take you from a starting
  value to an ending value over N years, if growth were steady.
- Why not just use plain average return: a fund that goes +50% then -50%
  looks like "0% average" but you actually lost money (50 → 75 → 37.5). CAGR
  captures compounding correctly; simple averaging doesn't.
- Formula: `(ending/beginning)^(1/years) - 1`

**Sharpe Ratio**
- What: return earned *per unit of risk taken*, risk being volatility
  (standard deviation of returns).
- Why it matters: two funds can have the same return, but one got there by
  swinging wildly and the other steadily — the steady one is "better" per
  unit of risk. Sharpe lets you compare that.
- Subtlety: subtracts a risk-free rate first (what you'd earn doing nothing,
  e.g. a T-bill) — you only care about *excess* return over the risk-free
  baseline.
- The code returns `None` instead of crashing when there isn't enough data
  or the fund had zero volatility — a UI-friendly way to say "N/A" instead
  of blowing up.

**Max Drawdown**
- What: the worst peak-to-trough drop an investor would have experienced if
  they bought at the worst possible time.
- Why it matters more than volatility alone for retail investors: it's the
  number that predicts whether someone panics and sells at the bottom.

**Database design choices worth understanding**
- Composite primary key on `(scheme_id, nav_date)` for the daily price table
  — makes sense because a single price on a single day for a single fund is
  naturally unique; no need for a separate auto-increment ID.
- `ON DELETE RESTRICT` (AMC → Scheme) vs `ON DELETE CASCADE` (user data):
  you never want deleting a fund house to silently wipe out fund records
  (that's a data-integrity bug waiting to happen), but you *do* want
  deleting a user to clean up their watchlist and transactions automatically.
- Separate `computed_metric_snapshot` table: metrics are *expensive* to
  compute (need full price history) but *cheap* to read — so they're
  precomputed by a background job and cached as rows, rather than calculated
  live on every API request.

**Why a background worker (Celery) instead of computing on request**
- Recomputing metrics from years of daily price data on every API call would
  be slow and wasteful, especially if 1000 users look at the same fund.
  Compute once (e.g. nightly), store the result, serve it instantly from
  cache/DB after that.

**Monorepo**
- One repo, multiple deployable pieces (API, worker, mobile app) plus a
  shared library (analytics-engine) all versioned and reviewed together.
  Tradeoff: simpler to keep things in sync across pieces vs. a "polyrepo"
  where each piece is its own repo (more autonomy, more coordination overhead).

### Interview questions to be able to answer out loud
1. Walk me through how you'd calculate a fund's annualized return, and why
   not just average the yearly percentage changes?
2. What does the Sharpe ratio actually measure, and when would a fund with
   lower returns have a *better* Sharpe ratio than one with higher returns?
3. Why might Sharpe ratio return "undefined" or "not meaningful" for some
   funds — what are the failure conditions?
4. What's max drawdown, and why do retail investors care about it more than
   they care about volatility (standard deviation)?
5. Why would you choose a composite primary key over a surrogate
   auto-increment key for time-series data?
6. Explain `ON DELETE CASCADE` vs `ON DELETE RESTRICT` — give a real example
   of when each is the wrong choice.
7. Why compute metrics in a background worker instead of on-demand in the
   API request handler? What are the tradeoffs (staleness vs. speed)?
8. What is a monorepo, and what problem is it solving here?

### Open questions / decisions to revisit
- Confirmed: API's `scheme_id` (string, e.g. "101206") maps to the DB's
  `amfi_scheme_code` column, NOT the integer primary key `Scheme.id`. Keep
  this straight when writing real queries later.
- Not yet decided: where real NAV data will come from (AMFI daily NAV file
  vs. an MFI API) — first real task for next session.

---

## Session 2 — Phase A Data Source Research

**Date:** 2026-07-26

### What we did
- Set up `shristi/setup` branch, confirmed collaborator write access, committed
  `learning.md`.
- Researched real data sources for mutual fund NAV (price) data ahead of
  writing the ingestion script.

### Concepts introduced this session

**Two different data sources, two different jobs**
- **AMFI's `NAVAll.txt`** (`https://www.amfiindia.com/spages/NAVAll.txt`):
  the official source of truth. Semicolon-delimited plain text, one row per
  scheme: `Scheme Code;ISIN Growth;ISIN Reinvestment;Scheme Name;NAV;Date`.
  Important limitation: this file is a **daily snapshot only** — it holds
  today's NAV for every scheme, not history. It also interleaves category
  headers (e.g. "Open Ended Schemes(Debt Scheme - Gilt Fund)") and AMC name
  headers as blank lines between data rows, so a naive line-by-line parser
  needs explicit logic to skip those.
- **mfapi.in** (`https://api.mfapi.in/mf/{scheme_code}`): a free, no-auth
  third-party API that has already parsed AMFI's full historical NAV per
  scheme into clean JSON (`{"meta": {...}, "data": [{"date": ..., "nav": ...}]}`).
  It's built on the same underlying AMFI data, just pre-assembled into
  history for you.

**Why we need both, not just one**
- AMFI's daily file → good for the *universe* of schemes (names, AMCs,
  categories) — matches the `amc`/`scheme` tables.
- mfapi.in → good for *backfilling history* per scheme — feeds
  `nav_history_daily`.
- Going forward (once a full history exists), only AMFI's *daily* file is
  needed to append one new row per scheme per day — no need to keep hitting
  a third-party historical endpoint indefinitely.

**A correctness subtlety for later (Phase B)**
- Some schemes show `NAV: 0.0000` in the live AMFI file — these are real
  zero NAVs from defunct/frozen "segregated portfolios" (e.g. old
  Franklin/UTI carve-outs tied to specific defaulted bonds like Vodafone
  Idea or Yes Bank), not bad data. Ingestion logic needs a deliberate
  decision here (skip / flag inactive) rather than silently computing CAGR
  on a fund that's actually worthless — a good "here's an edge case I
  handled" interview story.

### Interview questions to be able to answer out loud
1. Why use two different data sources instead of one? What's each one
   responsible for?
2. What would break if you assumed AMFI's daily file contained historical
   data?
3. How would you design the ingestion so today's daily update doesn't
   require re-fetching a scheme's entire history every time?
4. A fund shows NAV = 0. Is that a data quality bug or a real value — how
   do you tell the difference, and what should the system do with it?

### Open questions / decisions to revisit
- Which schemes to backfill first — full universe (~18,000 schemes) vs. a
  curated starter set? **Decided:** curated set of ~24 funds across 8
  categories (Large Cap, Flexi Cap, Mid Cap, Small Cap, ELSS, Debt-Short
  Duration, Hybrid/Balanced Advantage, Index Fund) — enough variety for
  Explore/Compare to feel real without full-universe ingestion overhead.
- **Important finding:** the scheme codes currently hardcoded in the stub
  data (`funds.py`, `compare.py` — e.g. `120503` used for "Parag Parikh
  Flexi Cap Fund") do NOT match the real AMFI scheme codes for those funds.
  These look like placeholder numbers, not verified codes. Do not reuse the
  existing stub scheme IDs when writing the ingestion script — resolve each
  fund's real scheme code fresh via mfapi.in's search endpoint
  (`/mf/search?q=...`) instead of hardcoding from memory.
- Next concrete coding step: a small standalone lookup script — fund name →
  mfapi.in search → confirmed real scheme code — as the first testable
  piece of the ingestion pipeline, before wiring anything to the database.

## Session 3 — Scheme Lookup Script

**Date:** 2026-07-26

### What we did
- Opened a PR (`shristi/setup` → `main`) so commits count toward GitHub
  contribution graph and to build the habit of working through PRs.
- Confirmed mfapi.in's search endpoint shape:
  `GET /mf/search?q=...` → `[{"schemeCode": ..., "schemeName": ...}]`
  (camelCase — inconsistent with the main NAV endpoint's snake_case
  `scheme_code`, worth remembering so it doesn't cause a silent bug).
- Wrote `scripts/lookup_schemes.py`: takes the curated list of ~24 fund
  names across 8 categories, searches mfapi.in for each, and writes out
  the top 3 fuzzy-matched candidates per fund to a JSON file for manual
  human review — deliberately does NOT auto-pick a scheme code, since
  that's exactly how the existing stub data ended up wrong.

### Concepts introduced this session

**Fuzzy string matching (`difflib.SequenceMatcher`)**
- What: compares two strings and returns a similarity ratio (0 to 1)
  based on matching subsequences, not exact equality.
- Why needed here: mfapi's search is loose (substring/keyword-ish), so a
  query like "Axis Bluechip Fund Direct Growth" might return several
  near-matches (Direct vs Regular plan, Growth vs IDCW option). Ranking
  by similarity surfaces the most likely correct match first, but a human
  still confirms it — the script explicitly avoids auto-accepting the
  top match.

**Defensive external API calls**
- The lookup function catches network errors and bad JSON per-request and
  returns an empty list instead of crashing the whole batch — so one flaky
  request doesn't lose the other 23 lookups. Small thing, but it's the
  same "fail gracefully, don't crash the whole pipeline" principle as
  Sharpe ratio's `None` return from last session.

**Why "resolve, don't hardcode"**
- This script produces output that still needs a human eyeball pass
  before being trusted — the design intentionally keeps a human in the
  loop for a one-time, high-stakes decision (which real scheme code maps
  to which fund) rather than fully automating something that's cheap to
  get wrong and expensive to have wrong silently (e.g. showing the wrong
  fund's returns to a user).

### Interview questions to be able to answer out loud
1. What is fuzzy string matching, and when would exact string matching be
   insufficient for a data resolution task like this?
2. Why does this script write a review file instead of directly writing
   confirmed scheme codes to the database?
3. Why catch exceptions per-item in a batch job instead of one try/except
   around the whole loop?
4. What's the risk of trusting an external free API's search ranking
   without any independent verification?

### Open questions / decisions to revisit
- After running `lookup_schemes.py` locally and reviewing
  `resolved_schemes.json`, next session's job is to write the actual
  ingestion script that takes the *confirmed* scheme codes and populates
  `amc`, `scheme`, and `nav_history_daily` via mfapi.in's history endpoint.
- **Major update — see below.** A pre-existing unmerged branch may already
  cover much of this. Confirm before writing new ingestion code from
  scratch.

### Addendum — CI investigation & major discovery (same session, PR #3 opened)

**CI failure triage:** PR #3's two failing checks are pre-existing issues
on `main`, unrelated to our changes (our PR only touched root-level
`learning.md` and `scripts/`, outside both linted directories):
- `API — Lint & Test` fails at the `ruff format --check` step — 4 files
  have lines that don't match the formatter's style (tests themselves
  pass, 7/7).
- `Analytics Engine — Lint & Test` fails at `ruff check` — import-order
  violations in `test_cagr.py` and `test_drawdown.py`. Both fixable with
  `ruff format .` / `ruff check --fix .` in seconds, whenever we get to
  Phase B polish.

**Major discovery:** an unmerged branch `copilot/implement-phase-2-application`
(PR #2, opened by the Copilot cloud agent, never merged — likely blocked
on an unapproved workflow-permissions gate) already contains real,
non-stub implementations of much of what we planned for Phase A, and
beyond:
- `apps/api/app/services/mfapi_client.py` — client for both AMFI's daily
  file and mfapi.in's history endpoint; defensively handles both APIs'
  inconsistent camelCase/snake_case field naming
- `apps/api/app/services/ingestion.py` — populates `AMC`/`Scheme` and
  syncs NAV history into the DB
- `apps/worker/app/tasks/metrics.py` — actually computes CAGR/Sharpe/
  Drawdown from real NAV history and writes to `computed_metric_snapshot`
  (this is the exact worker logic we were planning to write ourselves)
- Also includes `watchlist.py`, `portfolio.py`, `notifications.py`,
  `exports.py` — reaching into what we'd scoped as Phase C/D

**Decision for next session:** do NOT merge this blindly. Review it
properly first — check correctness (does it handle the zero-NAV /
defunct-scheme edge case we found in Session 2?), check test coverage,
understand the design before adopting any of it. The value of this
project is understanding the code well enough to defend it in an
interview, not having more code exist. Treat this as a code review
session, not a merge-and-move-on session.

## Session 4 — Data Source Switch to Tigzig + Ownership Decision

**Date:** 2026-07-26

### What we did
- Gaurav's decision on PR #2: use it as a design reference only, don't merge
  or reuse the code directly — build the implementation ourselves so both
  of us can actually own and defend it.
- Discovered and live-tested a better data source: **Tigzig's MF NAV API**
  (`https://api.tigzig.com/mf/v1/`), an alternative to mfapi.in.
- Switched `scripts/lookup_schemes.py` from mfapi.in to Tigzig.

### Concepts introduced this session

**Comparing data providers on real evidence, not just docs**
- Live-tested `GET /mf/v1/nav?scheme=118955&since=2020-01-01` — confirmed
  Tigzig returns NAVs as actual numbers (`712.78`), not strings like
  mfapi.in (`"77.69770"`). Small thing, but it means no manual type
  conversion (`float(nav)`) scattered through the ingestion code.
- Tigzig's NAV endpoint accepts **up to 50 scheme codes in a single call**
  (`schemes=118955,120468,...`) — our entire 24-fund backfill could be one
  API call instead of 24 sequential ones. Fewer requests, less code, fewer
  places for a network error to strike.
- Tigzig publishes real rate limits (300 req/min/IP on data endpoints) —
  removed the artificial delay we'd put in defensively for mfapi.in.

**Why "test it live" beats "read the docs and trust it"**
- We didn't just pick Tigzig because its marketing page sounded better —
  we made an actual `web_fetch` call to its live endpoint and inspected the
  real JSON shape before committing the script to it. Docs can describe an
  aspirational API; a live response is what your code will actually get.

### Interview questions to be able to answer out loud
1. You're choosing between two APIs that serve the same underlying data —
   what would you actually test before picking one, beyond reading docs?
2. Why does a batch endpoint (fetch 50 schemes in one call) matter for a
   pipeline like this, beyond "fewer lines of code"?
3. What's the practical cost of an API returning numbers as strings, and
   where would that cost show up later if unhandled?

### Open questions / decisions to revisit
- `/mf/v1/search`'s exact response field names weren't independently
  verified live (only `/mf/v1/nav` was) — `lookup_schemes.py` is written
  defensively (tries a couple of plausible key names) but this needs
  confirming and simplifying after the first real local run.
- Next session: run the updated script, review `resolved_schemes.json`,
  then write the actual ingestion script using Tigzig's batch NAV endpoint
  to populate `amc`/`scheme`/`nav_history_daily` — built independently,
  using PR #2 only as a design reference (e.g. "reuse `analytics_engine`,
  don't reimplement the math" is worth keeping as a pattern).

### Addendum — the "no candidates" mystery, solved (same session)

Ran the updated Tigzig script — 19/24 funds resolved cleanly, but 5 came
back empty, and **the exact same 5 failed on both mfapi.in and Tigzig in
separate runs**. Two independent providers agreeing on "no match" ruled out
a provider-specific bug — pointed at our search strings instead.

**Root cause, confirmed via research — 4 renames total, all now fixed:**
- `Axis Bluechip Fund` → `Axis Large Cap Fund` (June 2, 2025)
- `Axis Long Term Equity Fund` → `Axis ELSS Tax Saver Fund` (Dec 8, 2023 —
  part of an industry-wide SEBI-driven ELSS renaming)
- `PGIM India Midcap Opportunities Fund` → `PGIM India Midcap Fund`
- `Axis Short Term Fund` → `Axis Short Duration Fund` (SEBI category-name
  standardization — same pattern as the ELSS rename)

All 4 confirmed via real sources (fund fact sheets / value research), not
guessed. `Kotak Emerging Equity` was left as a simplified search term
without a confirmed rename — that one's a genuine "the exact suffix
matters to the search" case rather than a rename, worth a final check on
next run but not chased further this session.

**Why this matters beyond just fixing 5 rows:** this is a real
data-quality problem the ingestion pipeline will hit again, permanently —
AMFI/fund-house renames happen regularly (SEBI category standardization,
AMC mergers like PGIM India's ownership change). A one-time hardcoded
fund list goes stale; production ingestion should resolve by scheme code
(stable) wherever possible, not by re-searching fund names each time.

### Interview questions (addendum)
1. Two different data providers both return empty for the same query —
   what does that tell you about where the bug likely is?
2. A fund's official name changes after your system already has data
   keyed to its old name — how would you design ingestion to be resilient
   to that, longer-term?

## Session 5 — Full Product Vision & Scope

**Date:** 2026-08-06

### What we did
- Stepped back from implementation to define the real product scope, since
  "resume-ready" turned out to mean something bigger than a demo pipeline.

### The full vision (stated by Shristi)
A genuine multi-user product, not a portfolio demo:
- User profiles / accounts (not yet in the schema — real net-new work)
- Saved favorite funds (watchlist — already modeled in the DB)
- Daily-refreshed data (the worker + ingestion pipeline we're building)
- Evaluation / recommendation of what's good to invest in
- Coverage of *all* existing India mutual funds, not just the curated 24
- Fund comparison
- A portfolio overlap detector — flag when different funds someone holds
  are secretly invested in the same underlying stock
- A frontend with real visual personality/branding (colors TBD later)

### Concepts introduced this session

**NAV data vs. holdings data are two different things**
- NAV tells you a fund's *value* went up or down.
- Holdings tell you *what the fund actually owns* (e.g. "8% in HDFC Bank").
- Overlap detection needs holdings, not NAV — a fund could have unrelated
  NAV movement patterns and still hold the same underlying stock as
  another fund. This is a genuinely separate data dimension, refreshed on
  a different cadence (funds disclose holdings monthly, not daily),
  requiring new schema: a `stock` table and a `scheme_holding` table
  (fund → stock → weight%), not just an extension of what exists.

**Scoping decision: holdings/overlap detection deprioritized to backlog**
- It's the single highest-risk, highest-complexity piece (new data
  source, new refresh cadence, cross-fund stock identity matching).
  Building the rest of the product first — and getting it solid — before
  adding this, rather than letting the hardest feature block everything
  else. A legitimate prioritization call, worth being able to explain as
  a deliberate trade-off in an interview, not an omission.

### Interview questions to be able to answer out loud
1. Why does detecting portfolio overlap across funds require different
   data than computing CAGR/Sharpe/Drawdown for a single fund?
2. You've scoped a feature that adds real complexity and a new data
   dependency — how do you decide whether to build it now or defer it?
3. What's the difference in refresh cadence between price data and
   holdings data for a mutual fund, and why does that matter for how
   you'd design the ingestion pipeline?

### Open questions / decisions to revisit
- Tigzig's docs reference a portfolio holdings/composition pipeline
  separate from their NAV API — not yet live-tested. Worth verifying
  when the backlog item is picked back up, so the data-source decision
  for holdings isn't made blind the way NAV almost was.
- Re-scoped roadmap below reflects the full vision minus holdings (see
  backlog line).

## Session 6 — Real Ingestion Script + a Correction

**Date:** 2026-08-06

### What we did
- **Correction:** Session 5 claimed "no users table at all" in the schema
  — that was wrong, caught by re-checking the actual model file before
  writing new code. `AppUser` already exists (`app_user` table: email,
  display_name, analysis_mode). Phase C (real user accounts) needs auth
  wired to it, not the table built from scratch. Lesson: re-verify
  assumptions against the actual code before planning around them,
  especially assumptions repeated confidently across sessions.
- Added an `amc` field to each entry in `lookup_schemes.py`'s
  `CURATED_FUNDS` (Tigzig's NAV data doesn't include AMC name, only
  scheme-level info — needed it for populating the `amc` table).
- Wrote `scripts/ingest_nav_data.py` — the real Phase A ingestion script.
  Independent, from-scratch work (not from PR #2, per Gaurav's call in
  Session 4).

### What the ingestion script does
1. Reads the human-reviewed `resolved_schemes.json`, takes the top-ranked
   candidate per fund
2. One batch call to Tigzig's NAV endpoint for all 24 scheme codes at once
   (not 24 separate calls)
3. Get-or-create `AMC` and `Scheme` rows
4. Inserts `NAVHistoryDaily` rows — **skips zero/invalid NAV values**
   rather than inserting them as real prices (the defunct-scheme edge
   case from Session 2, finally implemented, not just discussed)
5. Safe to re-run: checks existing `(scheme_id, nav_date)` rows before
   inserting, so running it twice doesn't duplicate or error

### Concepts introduced this session

**Reusing real ORM models instead of redefining them in a script**
- The script adds `apps/api` to `sys.path` and imports the actual
  `AMC`/`Scheme`/`NAVHistoryDaily` SQLAlchemy models rather than writing
  parallel dataclasses. Redefining the schema in two places is a
  guaranteed way for them to quietly drift apart over time.

**Idempotency — designing a script to be safely re-run**
- `insert_nav_rows` checks which `(scheme, date)` pairs already exist
  before inserting. Without this, running the script twice would either
  crash on a duplicate primary key or, worse, silently double-count data.
  A pipeline you expect to run repeatedly (daily, or by hand while
  debugging) should be safe to run more than once.

**Separating "get the right data in" from "compute things from it"**
- Ingestion intentionally does NOT compute CAGR/Sharpe/Drawdown — that
  stays the worker's job. If a metric looks wrong later, this separation
  makes it possible to check "is the raw data wrong, or is the
  computation wrong?" as two independent questions instead of one
  tangled one.

**AMC code as a stand-in, flagged not hidden**
- The `amc` table requires a unique `amfi_code`, but Tigzig's data
  doesn't give us AMFI's actual AMC code — only the fund house's name.
  The script slugifies the name as a placeholder and says so in a
  comment, rather than silently treating a made-up value as real data.
  A good habit: when you have to fill a gap with something you're not
  fully confident in, say so in the code, don't just make it look correct.

### Interview questions to be able to answer out loud
1. Why import the real ORM models into a standalone script instead of
   just writing raw SQL or redefining lightweight versions of them?
2. What does "idempotent" mean for a data pipeline, and what breaks if a
   script like this isn't?
3. Why keep ingestion and metric computation as separate steps rather
   than computing CAGR immediately after inserting each NAV row?
4. You need a value your data source doesn't actually provide (AMC code)
   — what are your options, and why pick a flagged stand-in over leaving
   the field null or guessing silently?

### How to run this (for Shristi/Gaurav, not just notes)
```bash
docker-compose up -d postgres redis
cd apps/api && alembic upgrade head && cd ../..
pip install requests sqlalchemy psycopg2-binary
python scripts/ingest_nav_data.py
```

### Open questions / decisions to revisit
- Tigzig's batch NAV response shape (`schemes` / `not_found` keys) is
  documented but not yet live-tested — `fetch_batch_nav()` is written
  defensively with fallbacks. First real run will confirm which shape
  actually comes back; simplify the function once known.
- AMC code is a slugified stand-in, not a real AMFI AMC code — fine for
  now, but worth sourcing properly before this goes further (e.g. Tigzig's
  scheme master / bulk download may have it).

### Addendum — first real run: a milestone, and a caught bug (same session)

**Milestone:** ran the real pipeline end to end for the first time.
Docker → Postgres → Alembic migrations → chunked Tigzig fetch → real
insert. **70,825 real NAV rows landed in the database.** Along the way,
fixed two real environment issues (not code bugs): Tigzig's actual batch
response nests `schemes` as a **list**, not a dict keyed by code (fixed
`fetch_batch_nav` to normalize either shape); and fetching full multi-year
history for 24 funds in one request timed out, fixed by chunking into
groups of 6 with retries rather than one giant call.

**The bug, caught by reading the output carefully, not by a test:**
7 of the 24 ingested funds were the **wrong fund entirely** — not close
matches, actually different funds:

| Wanted | Actually got | Why |
|---|---|---|
| ICICI Prudential Bluechip Fund | ICICI Prudential **US** Bluechip Equity Fund | different country/asset class (also: real rename to "ICICI Prudential Large Cap Fund", confirmed June 16 2025 — same industry-wide pattern as Sessions 4) |
| Kotak Emerging Equity Fund | Kotak Global Emerging Market **Overseas** Equity FOF | different fund category entirely |
| Axis Short Duration Fund | Axis **Ultra** Short Duration Fund | different debt sub-category |
| UTI Nifty 50 Index Fund | UTI Nifty **Next** 50 Index Fund | tracks different 50 companies |
| HDFC Index Fund Nifty 50 | HDFC NIFTY **Next 50** Index Fund | same issue |
| ICICI Prudential Nifty 50 Index Fund | ICICI Prudential Nifty **500** Index Fund | 50 stocks vs 500 stocks |
| Quant Tax Plan | **Quantum** ELSS Tax Saver Fund | **two entirely different, unrelated AMCs** |

**Root cause:** the auto-pick-top-candidate approach trusted text
similarity (`difflib`) too much. Names that share most of their words but
differ in one meaningful qualifier ("Next", "500", "Ultra", "US",
"Quantum" vs "Quant") can out-score the actually-correct fund. The script
had a comment saying "human picks the right one, do not auto-accept" —
but nothing *enforced* that. A comment isn't a safeguard.

### The fix: an actual enforced checkpoint, not a comment
- `lookup_schemes.py` now writes `"confirmed_scheme_code": null` on every
  entry — deliberately never auto-filled, even when the top candidate
  looks obviously right.
- `ingest_nav_data.py`'s `load_confirmed_funds()` now **refuses** to use
  any entry where `confirmed_scheme_code` is still null, or where it
  doesn't match one of that entry's real candidates (catches typos too).
  It prints exactly what got skipped and why.
- New: `scripts/confirm_schemes.py` — an interactive tool that shows each
  fund's real candidates one at a time and makes a human actually pick.
  Saves after every single choice, safe to stop and resume.

### Concepts introduced this session

**A code comment is not a control** — "do not auto-accept" as a comment
next to code that *does* auto-accept is worse than no comment at all,
because it creates false confidence that the risk was handled. If a step
genuinely requires a human decision, the code needs to structurally
refuse to proceed without one (a null check that blocks execution), not
just say so in a docstring.

**Text similarity ranking has a specific blind spot: differentiating
qualifiers.** Two names sharing 90% of their words can still refer to
completely different products if the other 10% is the part that matters
("Next", "500", "Ultra", "US"). This is a general lesson beyond mutual
funds — any fuzzy-matching pipeline (product catalogs, entity resolution,
deduplication) has this exact failure mode.

**Idempotent pipelines make mistakes cheap to fix.** Because ingestion
checks existing `(scheme, date)` pairs before inserting, and because this
is local dev data, fixing this bug is just: wipe the dev DB, fix the
data, re-run. No delicate surgical row-by-row correction needed. Designing
for cheap re-runs earlier paid off immediately here.

### Interview questions to be able to answer out loud
1. Walk me through a real bug you caught in this project — what was it,
   how did you find it, and how did you fix the root cause vs. the symptom?
2. Why is "the code has a comment saying a human should check this" not
   the same as actually requiring human review?
3. What's a blind spot of similarity-based fuzzy matching that exact-match
   or keyword search wouldn't have, and vice versa?
4. Why does making a pipeline idempotent (safe to re-run) matter beyond
   just "convenience" — how did it directly help recover from this bug?

### Next session
1. Wipe the dev DB (`docker-compose down -v` → `up -d` → `alembic upgrade
   head`) — cheap, since it's local dev data.
2. Re-run `lookup_schemes.py` to regenerate `resolved_schemes.json` with
   the new `confirmed_scheme_code` field.
3. Run `scripts/confirm_schemes.py` and actually confirm all 24 by hand.
4. Re-run `ingest_nav_data.py` — now hard-gated, will refuse anything
   unconfirmed.

## Roadmap (living — update as phases complete)

- [ ] **Phase A — Core NAV pipeline:** ingest real NAV data for the 24
      curated funds, wire worker to compute real metrics and save them,
      make API read from DB *(in progress)*
- [ ] **Phase B — Make it correct:** handle short-history funds, missing
      trading days, fund renames/mergers; add integration tests
- [ ] **Phase C — Real user accounts:** users table, auth, watchlist/
      portfolio actually tied to logged-in users
- [ ] **Phase D — Full India MF universe ingestion:** expand beyond the
      curated 24 to the full ~8,600 active schemes
- [ ] **Phase E — Recommendation + comparison engine**
- [ ] **Phase F — Frontend design system + real UI build-out**
- [ ] **Phase G — Deployment**
- [ ] **Backlog — Holdings/composition data + overlap detector:**
      deliberately deprioritized (see Session 5) — revisit once the core
      product is solid