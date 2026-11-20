from fastapi import APIRouter

from tick.api.v1.endpoints.capabilities import router as capabilities_router
from tick.api.v1.endpoints.health import router as health_router
from tick.api.v1.endpoints.instruments import router as instruments_router
from tick.api.v1.endpoints.ohlcv import router as ohlcv_router

router = APIRouter()
## 健康检查
router.include_router(health_router)
## 标的路由
router.include_router(instruments_router)
## 行情路由
router.include_router(ohlcv_router)
## 能力路由
router.include_router(capabilities_router)
