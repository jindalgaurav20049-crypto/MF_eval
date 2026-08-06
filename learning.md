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

**Root cause, confirmed via research:** real mutual funds get renamed.
- `Axis Bluechip Fund` → `Axis Large Cap Fund` (effective June 2, 2025)
- `Axis Long Term Equity Fund` → `Axis ELSS Tax Saver Fund` (effective
  December 8, 2023 — part of an industry-wide SEBI-driven rename of ELSS
  fund names)

Both are fixed in `CURATED_FUNDS` now. The other 3 stubborn ones (Kotak
Emerging Equity, PGIM India Midcap Opportunities, Axis Short Term) got
simplified search terms rather than a guessed rename — worth checking
these properly on the next run rather than assuming.

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

## Roadmap (living — update as phases complete)

- [ ] **Phase A — Make it real:** ingest real AMFI NAV data, wire worker to
      compute real metrics and save them, make API read from DB
- [ ] **Phase B — Make it correct:** handle short-history funds, missing
      trading days, fund renames/mergers; add integration tests
- [ ] **Phase C — Make it defensible:** auth for watchlist/portfolio,
      Redis caching strategy, CI pipeline (GitHub Actions)
- [ ] **Phase D — Make it presentable:** live deployment, one fully
      end-to-end polished feature (likely Compare)