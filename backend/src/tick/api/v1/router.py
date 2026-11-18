from fastapi import APIRouter

from tick.api.v1.endpoints.health import router as health_router
from tick.api.v1.endpoints.instruments import router as instruments_router

router = APIRouter()
router.include_router(health_router)
router.include_router(instruments_router)
