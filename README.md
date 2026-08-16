# FundLens

> See through the noise.

FundLens is a fully free, open mutual fund evaluation platform built for Indian investors. Both Beginner and Advanced modes are completely unlocked.

The product has two complementary ways to discover funds:

- **Personalized Home:** "Help me decide." FundLens uses investor context to prioritize relevant information and recommendations.
- **Search:** "I know what I want." Users can directly search for any supported mutual fund scheme. Personalization must never block access to an explicitly requested fund.

Once a fund is selected, both paths lead to the same Fund Detail experience, presented in Beginner or Advanced mode.

---

# Monorepo Structure

```text
fundlens/
├── apps/
│   ├── api/                 # FastAPI backend
│   ├── worker/              # Celery background worker
│   └── mobile/              # React Native / Expo app
├── packages/
│   └── analytics-engine/    # Python metric computation library
├── docker-compose.yml
├── README.md                # Master roadmap + project tracker
└── FRONTEND_README.md       # Detailed frontend / UX specification
```

---

# Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 8+
- Docker & Docker Compose

---

# Quick Start

## 1. Install

```bash
pnpm install

cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..

cd apps/worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..

cd packages/analytics-engine
pip install -e ".[dev]"
cd ../..
```

## 2. Environment

```bash
cp apps/api/.env.example apps/api/.env
cp apps/worker/.env.example apps/worker/.env
cp apps/mobile/.env.example apps/mobile/.env
```

## 3. Infrastructure

```bash
docker-compose up -d postgres redis
```

## 4. Migrations

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
```

## 5. API

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## 6. Worker

```bash
cd apps/worker
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

## 7. Mobile

```bash
cd apps/mobile
pnpm install
pnpm start
```

---

# Tests

## Analytics Engine

```bash
cd packages/analytics-engine
pytest
```

## API

```bash
cd apps/api
pytest
```

---

# Current API Surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/funds/search` | Search mutual fund schemes |
| GET | `/funds/{scheme_id}/summary` | Fund summary |
| GET | `/compare` | Compare funds |

Example:

```bash
curl "http://localhost:8000/funds/search?q=axis+bluechip"
curl "http://localhost:8000/funds/101206/summary?mode=beginner"
curl "http://localhost:8000/funds/101206/summary?mode=advanced"
curl "http://localhost:8000/compare?scheme_ids=101206,119598"
```

---

# Product Architecture

```text
                         USER
                           |
              +------------+------------+
              |                         |
              v                         v
       PERSONALIZED HOME             SEARCH
       "Help me decide"        "I know what I want"
              |                         |
       recommendations          requested scheme
       + user context                    |
              |                         |
              +------------+------------+
                           |
                           v
                      FUND DETAIL
                           |
                  +--------+--------+
                  |                 |
                  v                 v
              BEGINNER          ADVANCED
                  |                 |
                  +--------+--------+
                           |
                           v
                    SAME ANALYTICS
```

## Core boundaries

### Search

Search answers:

> **Which fund did the user explicitly ask to see?**

Personalization must not remove or suppress an explicitly requested fund.

### Recommendations

Recommendations answer:

> **Which funds might be relevant when the user does not know what they want?**

### Personalization

Personalization answers:

> **Given this user's context, what information should appear first and how deeply should it be explained?**

It can change:

- Metric ordering
- Default charts
- Explanation depth
- Recommendation ranking
- Beginner/Advanced starting mode
- Contextual insights

It must not silently block explicit search access.

### Analytics engine

The analytics engine is responsible for financial calculations.

The frontend presents and explains those results.

Do not duplicate financial calculations in UI components.

---

# MASTER IMPLEMENTATION ROADMAP

This is the **single project-level progress tracker**.

`README.md` controls project sequencing and overall status.

`FRONTEND_README.md` contains the detailed frontend and UX build specification.

Do not create another master tracker.

Use the phases below in order because later work depends on earlier data, analytics, APIs and product contracts.

---

# PHASE 0: Foundation

## Objective

Make the repository reproducible and establish shared contracts.

### Repository

- [ ] Clean checkout installs successfully.
- [ ] PostgreSQL starts.
- [ ] Redis starts.
- [ ] API starts.
- [ ] Worker starts.
- [ ] Mobile app starts.
- [ ] Existing tests run.

### Shared contracts

- [ ] Canonical `scheme_id` defined.
- [ ] Normalized fund/scheme model defined.
- [ ] API response conventions defined.
- [ ] API error model defined.
- [ ] Date/period conventions defined.
- [ ] Beginner/Advanced mode contract defined.
- [ ] `UserContext` defined.
- [ ] `PresentationProfile` defined.

### Done when

A new contributor can clone the repo, run it locally and understand the shared contracts without undocumented instructions.

---

# PHASE 1: Mutual Fund Data Ingestion

## Objective

Create reliable normalized scheme and historical data.

### Tasks

- [ ] Select/document authoritative data sources.
- [ ] Implement scheme master ingestion.
- [ ] Implement NAV/history ingestion.
- [ ] Normalize AMC, scheme, category, plan and option.
- [ ] Store canonical `scheme_id`.
- [ ] Handle duplicate schemes.
- [ ] Handle merged/discontinued schemes.
- [ ] Store source and freshness metadata.
- [ ] Add ingestion validation tests.
- [ ] Add repeatable ingestion job/command.

### Done when

A known scheme can be queried with traceable identity, source and historical data.

---

# PHASE 2: Analytics Engine

## Objective

Build the financial calculation layer independently of the UI.

### Tasks

- [ ] CAGR / annualized return.
- [ ] Absolute return where applicable.
- [ ] Volatility.
- [ ] Sharpe ratio.
- [ ] Sortino ratio.
- [ ] Maximum drawdown.
- [ ] Drawdown duration.
- [ ] Recovery period.
- [ ] Benchmark-relative return.
- [ ] Rolling returns.
- [ ] Period validation.
- [ ] Missing-data handling.
- [ ] Unit tests.
- [ ] Methodology documentation.

### Hard rule

The same financial calculation must not be independently recreated in multiple frontend components.

### Done when

Known inputs produce deterministic, tested outputs that can be consumed by the API.

---

# PHASE 3: Core API

## Objective

Expose fund data and analytics through stable contracts.

### Tasks

- [ ] `/health`.
- [ ] `/funds/search`.
- [ ] `/funds/{scheme_id}/summary`.
- [ ] `/compare`.
- [ ] Analytics-engine integration.
- [ ] Invalid scheme handling.
- [ ] Invalid date/mode handling.
- [ ] API tests.
- [ ] API examples/documentation.

### Done when

Frontend can consume real fund data and tested metrics without calculating financial metrics itself.

---

# PHASE 4: Search & Fund Discovery

## Objective

Let users access any supported fund scheme they explicitly want.

### Frontend

- [ ] SearchBar.
- [ ] SearchInput.
- [ ] SearchResultCard.
- [ ] Scheme/AMC/category/plan/option display.
- [ ] Loading state.
- [ ] Empty state.
- [ ] No-results state.
- [ ] Error state.
- [ ] Real `/funds/search` integration.
- [ ] Search result → `scheme_id`.
- [ ] `scheme_id` → Fund Detail.

### Backend

- [ ] Scheme-name search.
- [ ] AMC/category search where appropriate.
- [ ] Unambiguous scheme identifiers.
- [ ] Search tests.

### Done when

A user can type a supported scheme name, identify the correct scheme and open its Fund Detail page.

---

# PHASE 5: Personalization Foundation

## Objective

Understand the investor enough to change information priority without creating a burdensome questionnaire.

### Initial UserContext

```text
Goal
Time horizon
Investment style / commitment
Knowledge level
Preferences
```

Do not collect unnecessary sensitive financial information during initial onboarding.

### Tasks

- [ ] WelcomeStep.
- [ ] GoalStep.
- [ ] HorizonStep.
- [ ] CommitmentStep.
- [ ] KnowledgeStep.
- [ ] PreferencesStep.
- [ ] ProfileConfirmation.
- [ ] Progress indicator.
- [ ] Back navigation persistence.
- [ ] "Just explore" path.
- [ ] UserContext persistence.
- [ ] Deterministic V1 personalization rules.
- [ ] PresentationProfile generation.

### Example rules

```text
IF knowledge = beginner
THEN explanation_depth = simple

IF horizon >= 10 years
THEN prioritize long_term_return

IF lower_volatility selected
THEN prioritize downside + volatility

IF retirement goal
THEN prioritize long_horizon_consistency
```

### Done when

Different UserContexts produce visibly different information priorities while the underlying fund data remains unchanged.

---

# PHASE 6: Beginner Experience

## Objective

Make serious financial information instinctively understandable.

Use the useful mechanics of gamified products:

- One clear objective at a time.
- Strong visual hierarchy.
- Immediate feedback.
- Progress indicators.
- Visual states.
- Clear next action.
- Progressive disclosure.

Do not turn investing into a game.

### Components

- [ ] GoalCard.
- [ ] VisualRating.
- [ ] MetricCard.
- [ ] InsightCard.
- [ ] ExplanationDrawer.
- [ ] SimpleChart.
- [ ] SelectionFeedback.
- [ ] Visual risk meter.
- [ ] Goal-fit visual.
- [ ] Growth journey visual.
- [ ] Drawdown story visual.
- [ ] Cost visual.

### Beginner Home

- [ ] Personalized greeting.
- [ ] Goal summary.
- [ ] Personalized fund section.
- [ ] One key insight.
- [ ] Search entry point.
- [ ] Beginner/Advanced switch.

### Beginner Fund Detail

- [ ] Fund identity.
- [ ] Goal fit.
- [ ] Historical performance.
- [ ] Downside.
- [ ] Consistency.
- [ ] Cost.
- [ ] "Why we showed you this".
- [ ] Explanation → evidence interaction.
- [ ] Advanced analysis entry.

### Done when

A financially inexperienced user can identify major performance, downside, consistency and relevance without first learning financial jargon.

---

# PHASE 7: Advanced Experience

## Objective

Give experienced users analytical depth without creating a second product.

### Tasks

- [ ] Mode switch.
- [ ] CAGR.
- [ ] Rolling returns.
- [ ] Volatility.
- [ ] Sharpe.
- [ ] Sortino.
- [ ] Maximum drawdown.
- [ ] Recovery period.
- [ ] Benchmark comparison.
- [ ] Portfolio/holdings.
- [ ] Date range.
- [ ] Chart controls.
- [ ] Metric visibility.
- [ ] Comparison entry point.

### Done when

Beginner and Advanced views of the same fund use consistent underlying values and calculations.

---

# PHASE 8: Comparison & Portfolio Intelligence

## Comparison

- [ ] Multi-fund selection.
- [ ] Common-period comparison.
- [ ] Return comparison.
- [ ] Risk comparison.
- [ ] Drawdown comparison.
- [ ] Benchmark comparison.
- [ ] Beginner comparison view.
- [ ] Advanced comparison view.

## Portfolio

- [ ] CAS import/parser.
- [ ] Portfolio normalization.
- [ ] Portfolio overlap.
- [ ] Concentration.
- [ ] Category/sector exposure.
- [ ] Portfolio-level risk.

### Done when

A user can compare funds and, when portfolio data is available, understand overlap and concentration.

---

# PHASE 9: Extended Intelligence

Build these only after core evaluation is reliable.

- [ ] Rolling-return heatmap.
- [ ] Tax scenario modeler.
- [ ] Fund-manager change tracking.
- [ ] SEBI event tracking.
- [ ] Watchlist.
- [ ] Push alerts.
- [ ] PDF export.
- [ ] Excel export.

Every feature must have:

- [ ] Data source.
- [ ] Methodology.
- [ ] API contract.
- [ ] UI states.
- [ ] Tests.
- [ ] Traceability where applicable.

### Done when

The feature works end-to-end with real data and handles missing/stale/failed data explicitly.

---

# PHASE 10: Behavioural Personalization

## Objective

Improve personalization using actual product behaviour only after deterministic V1 rules are stable.

### Events

- [ ] `onboarding_completed`
- [ ] `fund_opened`
- [ ] `metric_opened`
- [ ] `explanation_opened`
- [ ] `advanced_mode_opened`
- [ ] `comparison_started`
- [ ] `comparison_completed`
- [ ] `filter_changed`
- [ ] `chart_interacted`
- [ ] `watchlist_added`
- [ ] Search events

### Personalization loop

```text
User context
    |
    v
Initial presentation
    |
    v
Observed behaviour
    |
    v
Preference signal
    |
    v
User-confirmed adjustment
    |
    v
Updated presentation profile
```

Do not silently make major changes based on weak behavioural evidence.

### Done when

Behaviour can improve information prioritization without changing financial calculations or restricting explicit fund access.

---

# PHASE 11: Production Hardening

### Tasks

- [ ] Full API tests.
- [ ] Analytics-engine tests.
- [ ] Frontend component tests.
- [ ] Critical user-flow tests.
- [ ] Accessibility audit.
- [ ] Mobile performance audit.
- [ ] API performance/load testing.
- [ ] Database backup strategy.
- [ ] Logging/monitoring.
- [ ] Error tracking.
- [ ] Security review.
- [ ] Data freshness monitoring.
- [ ] CI.
- [ ] CD.
- [ ] Production configuration.

### Done when

A production deployment can be built reproducibly, critical flows are tested, failures are observable and stale/invalid financial data is not silently presented as current.

---

# Master Progress Board

Update this board whenever a phase materially changes.

```text
[ ] Not started
[~] In progress
[x] Complete
[!] Blocked

PHASE 0   Foundation                  [ ]
PHASE 1   Data Ingestion              [ ]
PHASE 2   Analytics Engine            [ ]
PHASE 3   Core API                    [ ]
PHASE 4   Search & Discovery          [ ]
PHASE 5   Personalization             [ ]
PHASE 6   Beginner Experience         [ ]
PHASE 7   Advanced Experience         [ ]
PHASE 8   Comparison & Portfolio      [ ]
PHASE 9   Extended Intelligence       [ ]
PHASE 10  Behavioural Personalization [ ]
PHASE 11  Production Hardening        [ ]
```

## Current Status

```text
Current phase: PHASE 0
Overall status: [ ] / [~] / [x] / [!]

Last meaningful milestone:
-

Current blockers:
-

Next concrete tasks:
-
-
-
```

---

# Contributor Workflow

```text
1. Read the phase in README.md
        |
        v
2. Read FRONTEND_README.md if it is frontend work
        |
        v
3. Pick one concrete unchecked task
        |
        v
4. Check dependencies
        |
        v
5. Build with mock data if upstream is unavailable
        |
        v
6. Implement loading / empty / error states
        |
        v
7. Connect the real contract
        |
        v
8. Add tests
        |
        v
9. Verify acceptance criteria
        |
        v
10. Update checklist + open PR
```

Do not build large disconnected features just because they look impressive.

---

# Definition of Done

A feature is complete only when applicable:

- [ ] UI implemented.
- [ ] Backend/API contract defined.
- [ ] Real or documented mock data used.
- [ ] Loading state implemented.
- [ ] Missing-data state implemented.
- [ ] Error state implemented.
- [ ] Financial methodology identified.
- [ ] Financial calculation is not duplicated in UI.
- [ ] Tests added.
- [ ] Accessibility checked.
- [ ] Mobile behaviour checked.
- [ ] Acceptance criteria demonstrated.
- [ ] Documentation updated.

---

# Frontend Specification

See [`FRONTEND_README.md`](FRONTEND_README.md) for:

- User onboarding.
- Beginner visual system.
- Gamified interaction patterns.
- Advanced interface.
- Search UX.
- Fund Detail architecture.
- Personalization architecture.
- Component structure.
- Concrete frontend build sequence.
- Usability testing.
- Frontend-specific progress tracking.

`README.md` is the **master project roadmap**.

`FRONTEND_README.md` is the **detailed frontend execution document**.

Do not create a third document for project progress.

---

# Architecture Notes

- **Database:** PostgreSQL 15 with optional TimescaleDB.
- **Cache:** Redis.
- **Task Queue:** Celery + Redis.
- **Mobile:** React Native + Expo.
- **Backend:** FastAPI.
- **Analytics:** Python analytics-engine package.

---

# Financial Integrity Rules

1. Do not invent financial data.
2. Do not fabricate missing metrics.
3. Do not silently substitute one metric for another.
4. Do not calculate the same financial metric independently in multiple frontend components.
5. Document methodology for every derived metric.
6. Use comparable periods and definitions when comparing funds.
7. Distinguish historical observations from predictions or recommendations.
8. A personalization score is a relevance/presentation mechanism, not a claim of future outperformance.
9. Search must provide explicit fund access.
10. When evidence is unavailable, say so.
