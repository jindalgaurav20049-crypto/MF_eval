"""FundLens API — FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import SessionLocal
from app.logging_config import configure_logging
from app.routers import compare, events, exports, funds, health, portfolio, watchlist
from app.services.funds_service import ensure_mf_universe

configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("fundlens_api_starting", environment=settings.app_env)
    if settings.auto_sync_mf_universe:
        db = SessionLocal()
        try:
            result = ensure_mf_universe(db)
            logger.info(
                "mf_universe_sync_completed",
                schemes_added=result.schemes_added,
                schemes_updated=result.schemes_updated,
                nav_rows_added=result.nav_rows_added,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("mf_universe_sync_failed", error=str(exc))
        finally:
            db.close()
    yield
    logger.info("fundlens_api_shutdown")


app = FastAPI(
    title="FundLens API",
    description="Mutual fund evaluation API for Indian investors. All features free, no paywall.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(funds.router)
app.include_router(compare.router)
app.include_router(portfolio.router)
app.include_router(events.router)
app.include_router(watchlist.router)
app.include_router(exports.router)
