import structlog
from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])
logger = structlog.get_logger(__name__)

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("health_check_called")
    return HealthResponse(
        status="ok",
        version=VERSION,
        environment=settings.app_env,
    )
