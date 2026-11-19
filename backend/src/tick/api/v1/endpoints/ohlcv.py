from fastapi import APIRouter, HTTPException, Path, Query

from tick.market.ohlcv_cache import get_ohlcv_1d_bars
from tick.schemas.ohlcv import OhlcvSeriesOut

router = APIRouter(tags=["ohlcv"])

_MAX_LIMIT = 5000


@router.get("/ohlcv/1d/{symbol}", response_model=OhlcvSeriesOut)
async def get_ohlcv_1d(
    symbol: str = Path(min_length=1, description="System symbol, e.g. 600519.SH"),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=_MAX_LIMIT,
        description="Optional: return only the most recent N bars. Omit for full series.",
    ),
) -> OhlcvSeriesOut:
    try:
        bars = get_ohlcv_1d_bars(symbol, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OhlcvSeriesOut(symbol=symbol, bars=bars)
