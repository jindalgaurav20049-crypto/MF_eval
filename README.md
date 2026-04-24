# FundLens

> See through the noise.

FundLens is a fully free, open mutual fund evaluation platform built for Indian investors. Both Beginner and Advanced modes are completely unlocked — no paywall, no subscription.

## Monorepo Structure

```
fundlens/
├── apps/
│   ├── api/           # FastAPI backend
│   ├── worker/        # Celery background worker
│   └── mobile/        # React Native mobile app
├── packages/
│   └── analytics-engine/  # Python metric computation library
├── docker-compose.yml
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 8+
- Docker & Docker Compose

## Quick Start

### 1. Clone and install dependencies

```bash
# Install JS dependencies (for mobile)
pnpm install

# Install Python dependencies for API
cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../..

# Install Python dependencies for Worker
cd apps/worker && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../..

# Install analytics engine in dev mode
cd packages/analytics-engine && pip install -e ".[dev]"
cd ../..
```

### 2. Configure environment

```bash
cp apps/api/.env.example apps/api/.env
cp apps/worker/.env.example apps/worker/.env
cp apps/mobile/.env.example apps/mobile/.env
```

Edit the `.env` files as needed (defaults work for local Docker setup).

### 3. Start local infrastructure

```bash
docker-compose up -d postgres redis
```

### 4. Run database migrations

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
```

### 5. Start the API

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API will be available at http://localhost:8000  
Interactive docs: http://localhost:8000/docs

### 6. Start the Worker

```bash
cd apps/worker
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

### 7. Start the Mobile App

```bash
cd apps/mobile
pnpm install
pnpm start
```

Follow Expo prompts to run on Android/iOS simulator or physical device.

## Running Tests

### Analytics Engine

```bash
cd packages/analytics-engine
pip install -e ".[dev]"
pytest
```

### API

```bash
cd apps/api
pytest
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/funds/search` | Search mutual fund schemes |
| GET | `/funds/{scheme_id}/summary` | Fund summary (beginner/advanced mode) |
| GET | `/compare` | Compare multiple funds |

### Example requests

```bash
# Health check
curl http://localhost:8000/health

# Search funds
curl "http://localhost:8000/funds/search?q=axis+bluechip"

# Fund summary (beginner mode)
curl "http://localhost:8000/funds/101206/summary?mode=beginner"

# Fund summary (advanced mode)
curl "http://localhost:8000/funds/101206/summary?mode=advanced"

# Compare funds
curl "http://localhost:8000/compare?scheme_ids=101206,119598"
```

## Architecture Notes

- **Database:** PostgreSQL 15 with optional TimescaleDB extension for time-series NAV data
- **Cache:** Redis for hot metric cache
- **Task Queue:** Celery with Redis broker for background metric computation
- **Mobile:** React Native with Expo for iOS/Android

## Known Follow-up Tasks (Phase 2)

- [ ] Implement actual MF data ingestion from AMFI / MFI API
- [ ] Implement metric computation engine (CAGR, Sharpe, Drawdown, etc.)
- [ ] Wire analytics-engine into API routes
- [ ] Implement rolling return heatmap endpoints
- [ ] Portfolio import via CAS parser
- [ ] Portfolio overlap analyzer
- [ ] Tax scenario modeler
- [ ] Fund manager change tracking
- [ ] SEBI regulatory event tracker
- [ ] Push notifications for watchlist alerts
- [ ] Export to PDF/Excel
- [ ] CI/CD deployment pipeline
