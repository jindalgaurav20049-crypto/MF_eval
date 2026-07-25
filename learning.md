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

## Roadmap (living — update as phases complete)

- [ ] **Phase A — Make it real:** ingest real AMFI NAV data, wire worker to
      compute real metrics and save them, make API read from DB
- [ ] **Phase B — Make it correct:** handle short-history funds, missing
      trading days, fund renames/mergers; add integration tests
- [ ] **Phase C — Make it defensible:** auth for watchlist/portfolio,
      Redis caching strategy, CI pipeline (GitHub Actions)
- [ ] **Phase D — Make it presentable:** live deployment, one fully
      end-to-end polished feature (likely Compare)