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

### Session 6 — Final Wrap (real data, confirmed, demoed)

Finished the confirmation pass by hand: worked through all remaining
entries applying the pattern learned across the session — **Growth
option, Direct plan, exact category match**, skip anything IDCW/Bonus/
Regular/Ultra/Next/500/Equal Weight/deactivated. Found one more real
rename along the way: **Kotak Emerging Equity Fund → Kotak Midcap Fund**
(confirmed via kotakmf.com, same ISIN throughout) — the 5th rename found
this project, same industry-wide pattern each time.

Also fixed a real bug in `lookup_schemes.py` itself: it originally
overwrote the whole output file on every run, which would have silently
wiped out confirmed answers if re-run to fix just one fund's search term.
Now merges — carries forward anything already confirmed, only re-fetches
what's still open.

**Final result: 24/24 funds confirmed, 73,587 real NAV rows ingested.**
PR #3 merged into `main`.

**Built `scripts/demo_metrics.py`** — pulls every ingested fund's real NAV
history and feeds it straight into the actual `analytics_engine` package
(same tested CAGR/Sharpe/Drawdown code from Session 1, nothing
reimplemented) to print a live comparison table. Caught one small real
gap while wiring it up: `cagr_from_nav_series` exists in
`analytics_engine.calculators.cagr` but was never re-exported at the
package's top level (`__init__.py`) — worth adding as a small follow-up,
since it's the more commonly useful entry point for callers who have a
NAV series rather than a bare start/end pair.

**The output passed a real sanity check**, not just "ran without
crashing": Small Cap funds showed the highest CAGR (22-24%) *and* the
deepest drawdowns (-34% to -48%) — exactly the risk/reward relationship
real markets should produce. Debt Short Duration sat at the calm end
(8% CAGR, 2-3% drawdown, Sharpe > 1.2). And the two known-wrong entries
(HDFC "Equal Weight" instead of plain Nifty 50, ICICI "Nifty 500" instead
of Nifty 50) stood out organically in the data itself — the ICICI one
showed only 1.6 years of history and a negative Sharpe ratio, consistent
with it being a newer, different fund than intended. The bug we already
knew about confirmed itself through the data, which is a good sign the
pipeline reflects reality rather than hiding problems.

### Interview questions (final addendum)
1. How do you sanity-check a data pipeline's output beyond "it ran
   without errors" — what would make you trust (or distrust) the numbers?
2. You found the same class of bug (wrong-fund matches) confirm itself
   organically in downstream computed metrics — what does that tell you
   about defense in depth in a data pipeline?
3. Walk through the small cap vs. debt fund risk/reward pattern in this
   data — why is that the expected relationship, and what would it mean
   if you saw the opposite?

### Known follow-ups (not blocking, logged so they aren't lost)
- Fix HDFC and ICICI's Nifty 50 Index Fund entries (currently ingested as
  Equal Weight and Nifty 500 respectively) — re-confirm and re-ingest
  just those two.
- Add `cagr_from_nav_series` to `analytics_engine`'s top-level exports.
- lookup_schemes.py's file-overwrite bug is fixed, but worth double-
  checking `confirm_schemes.py`'s incremental-save behavior wasn't
  affected by the same class of issue.

## Session 7 — API Wired to Real Data (Phase A Complete)

**Date:** 2026-08-08

### What we did
Replaced all stub API responses with real database queries:
- `/funds/search` — real `Scheme`/`AMC` query with `ilike` matching, live
  latest-NAV lookup per result
- `/funds/{id}/summary` — real CAGR/Sharpe/Drawdown computed live from
  ingested NAV history, with proper 1Y/3Y/5Y trailing windows for
  advanced mode (not just one full-history number)
- `/compare` — same underlying computation, reused via a new shared
  `app/services/fund_metrics.py` rather than duplicated per-endpoint
- Fixed 3 existing tests that hardcoded fake placeholder scheme codes
  (`101206`) — replaced with real confirmed codes from Session 6

Verified live: `GET /funds/search?q=axis` returned 5 real Axis funds
across 5 different categories with real current NAV values, straight
from the database.

### Concepts introduced this session

**Trailing windows vs. full-history metrics are genuinely different
things.** `demo_metrics.py` computes one CAGR/Sharpe/Drawdown per fund
over its *entire* history (13+ years for most funds) — useful as an
end-to-end pipeline proof, but not what "what's this fund's 1-year
return" actually means. The real API's advanced summary slices the NAV
series into proper 1Y/3Y/5Y trailing windows and computes each
independently — the difference between a demo script and a real feature.

**A dependency injection pattern for DB access (`Depends(get_db)`).**
FastAPI's `Depends` mechanism opens a DB session per-request and
guarantees it closes afterward (via `try/finally`) even if the request
handler raises an exception. Without this, a bug in one request could
leak an open DB connection that never gets cleaned up.

**Flag gaps in code, don't hide them.** Several fields (expense ratio,
AUM, benchmark comparison, sub-category) return `None` with an inline
comment explaining exactly why ("not ingested yet") rather than a fake
plausible-looking number. The health score is explicitly labeled a
"deliberately simple placeholder, not a validated methodology" in its
own docstring — anyone reading the code (including future us) knows
immediately what's real and what's a stand-in.

**A real, logged limitation: tests now depend on a live database.**
The existing test suite hits the actual Postgres instance directly, no
mocking or fixtures. Passes locally (DB is populated), but will **fail
in CI** since GitHub Actions has no database at all. Correct proper fix
(isolated test DB / fixtures) is real Phase B work, not done today —
logged here so it isn't forgotten or discovered as a surprise later.

### Interview questions to be able to answer out loud
1. Why compute metrics over trailing windows (1Y/3Y/5Y) instead of one
   full-history number — what does each serve that the other doesn't?
2. Explain what `Depends(get_db)` actually does and why the
   `try/finally` matters — what breaks without it?
3. Why return `None` for a field you don't have data for, instead of a
   reasonable-looking estimate? What's the cost of doing it the other way?
4. Your test suite passes locally but would fail in CI — why, and what's
   the actual fix (not just "add a database to CI")?

### Known follow-ups (not blocking, logged so they aren't lost)
- Fix HDFC and ICICI's Nifty 50 Index Fund entries (still wrong from
  Session 6 — Equal Weight / Nifty 500 instead of plain Nifty 50)
- Test suite needs isolated fixtures, not a dependency on the live dev DB
- `analytics_engine` should re-export `cagr_from_nav_series` at its
  top level (Session 6 finding, still open)
- Worker (`apps/worker/app/tasks/metrics.py`) still doesn't persist
  computed metrics into `computed_metric_snapshot` — summary/compare
  endpoints compute live on every request, which works for a demo but
  won't scale as a caching strategy

### Addendum — caught our own bug by actually reading the response (same session)

First live test of `/compare` returned `return_3y_cagr_pct`/`return_5y_cagr_pct`
as `null` for both funds — a stub `None` left in `compare.py` that never
got wired up, missed during the original build. Caught by reading the
actual JSON response critically rather than just checking the request
succeeded (status 200 isn't the same as "the response is correct" — the
same lesson from Session 6's wrong-fund matches, applied one layer up).

Fixed by reusing `trailing_window()` + `compute_metrics()` (already built
for `funds.py`'s summary endpoint) inside `compare.py`'s `_build_slot()`.
Also caught a second, related bug while fixing the first: `std_dev_3y`
and `sharpe_3y` were named for a 3-year window but were being fed
full-history values — an easy mistake since both existed as valid
numbers, just the wrong ones for what the field name promised. Verified
the fix with a live before/after comparison: 3Y-window Sharpe (0.41) vs.
the full 13-year Sharpe (0.55) for the same fund — genuinely different
numbers, confirming the fix changed the actual calculation, not just
silenced a null.

**Lesson:** a field returning a plausible-looking number is not the same
as a field returning the *correct* number for what its name promises —
worth checking field-by-field against what each name actually claims,
not just "did every field get filled in."

## Session 8 — Final Data Cleanup + Replanning

**Date:** 2026-08-09

### What we did
Tried to fix the last 2 known-wrong funds (HDFC and ICICI's Nifty 50
Index Fund, wrong since Session 6). This turned into real API
archaeology, then a deliberate decision to stop.

### What happened, in order
1. Investigated expense ratio as a "quick win" — turned out AMFI's TER
   page is a JS-driven form, not a flat file like NAVAll.txt. Genuinely
   not a quick add; needs its own investigation session. Logged, not
   pursued further today.
2. For the 2 wrong funds: their real names didn't appear in Tigzig's
   search results under any name-text variant tried. Found verified
   ISINs from independent sources (HDFC: `INF179K01WM1`, ICICI:
   `INF109K012M7`, each cross-confirmed via 3-4 sources).
3. **Wrong assumption caught mid-stream:** first tried searching
   `/mf/v1/search?q=<ISIN>` — got zero results. Tigzig's own docs
   confirmed ISIN support exists, but only on `/mf/v1/nav`, not
   `/search`. Search only ever matched fund-name text.
4. Manually set `confirmed_scheme_code` to the ISINs directly (bypassing
   search, since the ingestion script's actual NAV fetch supports ISIN
   natively) — but mixing an ISIN into the same batch request as 5
   numeric codes caused that request to hang indefinitely.
5. **Fixed properly:** split ingestion so numeric codes still batch
   together (proven, fast) but ISIN-based codes fetch individually,
   isolated — so one identifier can't freeze the whole run.
6. Re-ran cleanly — batch numeric funds correctly showed **"+1 row"**
   each (not a bug: idempotency working exactly as designed, only
   inserting the 1 new day since the last successful run). Both ISINs
   came back "not found" — cleanly, not hanging.
7. **Final decision: dropped both funds from the curated list.** Per
   Tigzig's own troubleshooting docs, a clean "not found" on a verified
   ISIN usually means it's the wrong fund *variant*, not a wrong code.
   Chasing 2 of 24 funds further wasn't worth more time — 22 real,
   correctly verified funds across 8 categories is a solid dataset.
   **Phase A is now genuinely, finally complete at 22 funds.**

### Concepts introduced this session

**Not every API "supports X" claim applies to every endpoint of that
API.** Tigzig's docs said "ISIN codes are fully supported" — true, but
only for `/nav`, not `/search`. A capability described for an API
doesn't automatically transfer to every endpoint in it; check which
specific endpoint the claim is about.

**Isolating unusual inputs prevents one edge case from breaking
everything else.** Mixing a rarely-used identifier format (ISIN) into a
batch request that otherwise only ever saw numeric codes was the kind of
untested combination that's easy to introduce without noticing. The fix
wasn't "add a longer timeout" — it was structural: never let an
unusual case share a request with the proven common case.

**Knowing when to stop is a real engineering skill, not a failure.**
Two funds out of 24 (8%) consumed a disproportionate amount of time.
Recognizing that and cutting losses — rather than continuing to
"just try one more thing" — is itself something worth being able to
talk about: scoping decisions aren't just made at the start of a
project, they get made continuously.

### Interview questions to be able to answer out loud
1. You found conflicting information about whether an API feature was
   supported — how did you resolve it, and what did you learn about
   trusting documentation at face value?
2. Describe a time you decided to stop debugging something and move on
   — what made you decide that, and how did you make sure it wasn't
   forgotten?
3. Why does isolating an unusual input from a batch of normal inputs
   improve reliability, even if it makes the code slightly more complex?

### Replanning — frontend and multi-user prioritized next

Full vision is roughly a third complete. Re-sequenced from the original
A→B→C→D order to match what's actually wanted next: real frontend and
real multi-user accounts, ahead of full-universe ingestion or the
recommendation engine — those need a working, demoable product to plug
into first.

## Session 9 — Frontend Wired to Real Data (Phase F Complete)

**Date:** 2026-08-15

### What we did
Discovered Home/Explore/Profile screens were already genuinely wired to
the real API from earlier work — the real gaps were a missing Fund
Detail screen and a placeholder Compare screen. Built both:
- Added real TypeScript interfaces (`BeginnerSummary`, `AdvancedSummary`,
  `CompareResponse`, etc.) matching the API's Pydantic schemas exactly —
  replaced `unknown` types that gave zero safety
- Built `FundDetailScreen.tsx` — real health score, verdict, and metrics,
  rendering differently for beginner vs. advanced mode
- Rebuilt `CompareScreen.tsx` — real fund search, add/remove selection,
  calls the actual `/compare` endpoint
- Restructured navigation so Explore is a stack (list → detail) instead
  of a flat tab, so tapping a search result actually goes somewhere
- Fixed 2 real bugs caught while building: `compare.py`'s `std_dev_3y`/
  `sharpe_3y` fields were fed full-history values instead of the 3-year
  window their names promised; a stray `unknown` type masked a missing
  field mapping

### The debugging trail (all real environment issues, not code bugs)
1. `EMFILE: too many open files` — macOS's file watcher limit hit by
   Metro; fixed with Watchman (the standard tool for this)
2. Favicon/icon crash — `app.json` referenced image files that were
   never created; generated placeholders
3. VSCode showing "cannot find module 'react'" everywhere — turned out
   to be a stray duplicate `src/` folder sitting at the repo root
   (outside `apps/mobile`), confusing the TypeScript checker; deleted
4. `500 Internal Server Error` on `/funds/search?q=hdfc` — traced via
   the actual server traceback (not guessed) to Postgres not running —
   same root cause as an earlier session, now a recognized pattern

**The pattern worth naming:** every one of these looked alarming on
first read (stack traces, red errors, "fetches none of the schemes") but
each had a boring, specific cause once actually investigated — wrong
directory, missing file, stale duplicate, service not running. None
were bugs in the code we wrote this session.

### Verified live
Screenshot evidence: Explore search for "hdfc" returned all 4 real HDFC
funds with real NAV values. Compare screen showed HDFC Nifty50 Equal
Weight vs. Axis ELSS Tax Saver side by side — genuinely different
1Y/3Y/5Y returns, Sharpe ratios (0.62 vs 0.49), drawdowns (-18% vs
-33.5%), and health scores (43 vs 48) for each fund. **First time the
actual app UI — not curl, not a demo script — showed real computed data
end to end.**

### Concepts introduced this session

**A 500 error's real cause lives in the server terminal, not the browser.**
The browser only ever shows a generic "Internal Server Error" — the
actual Python traceback with the real exception type and line number is
printed wherever `uvicorn` is running. Always go there first instead of
guessing from the client side.

**Isolating suspects one at a time beats guessing at everything.**
Rather than assuming the frontend broke, we tested the backend URL
directly in a browser first — separating "is this a data/backend
problem" from "is this a frontend problem" before touching any code.

**A duplicate/stray file can shadow the real one for tooling.**
VSCode's TypeScript checker was reading a leftover copy of files outside
the actual project folder, producing errors that had nothing to do with
the real, working code sitting in the right place.

### Interview questions to be able to answer out loud
1. A browser shows "Internal Server Error" with no detail — where do you
   actually look, and why does the browser not show you more?
2. Walk through how you isolated whether a bug was in the frontend or
   backend, rather than guessing at both simultaneously.
3. Why might a code editor show import errors for a project that
   actually type-checks and runs fine from the terminal?

## Roadmap (living — update as phases complete)

- [x] **Phase A — Core NAV pipeline:** 22 real, verified funds ingested
      across 8 categories, API reads from DB, real metrics computed live
      via analytics_engine — **complete as of Session 8**
- [x] **Phase F — Frontend build-out:** Explore search, Fund Detail, and
      Compare all verified live against real data — **complete as of
      Session 9**
- [ ] **Phase C — Multi-user + auth** *(prioritized next)*: `app_user`
      table already exists — needs real login/session handling,
      watchlist/portfolio actually tied to logged-in users
- [ ] **Phase B — Make it correct:** isolated test fixtures (not a live
      DB dependency), handle short-history funds, missing trading days,
      persist worker-computed metrics into computed_metric_snapshot
      instead of computing live every request
- [ ] **Phase D — Full India MF universe ingestion:** expand beyond the
      curated 22 to the full ~8,600 active schemes
- [ ] **Phase E — Recommendation + comparison engine** — good candidate
      for Gaurav to lead the product-thinking side of
- [ ] **Phase G — Deployment**
- [ ] **Backlog — Holdings/composition data + overlap detector:**
      deliberately deprioritized (see Session 5); Tigzig's "Composition"
      tool (found Session 8) is a likely real data source when revisited
- [ ] **Backlog — Expense ratio data:** AMFI's TER page is a JS form, not
      a flat file — needs its own investigation session (Session 8)