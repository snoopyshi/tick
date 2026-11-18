from fastapi import APIRouter

from tick import __version__
from tick.core.config import settings
from tick.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(version=__version__, environment=settings.environment)
