from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query

from tick.market.adjust_view import forward_adjust
from tick.market.factor_cache import get_factor_cache
from tick.market.ohlcv_cache import get_ohlcv_1d_bars, get_ohlcv_1d_cache
from tick.schemas.ohlcv import OhlcvSeriesOut

router = APIRouter(tags=["ohlcv"])

_MAX_LIMIT = 5000
_FACTORS_UNAVAILABLE = "adjust factors unavailable"


@router.get("/ohlcv/1d/{symbol}", response_model=OhlcvSeriesOut)
async def get_ohlcv_1d(
    symbol: str = Path(min_length=1, description="System symbol, e.g. 600519.SH"),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=_MAX_LIMIT,
        description=(
            "Optional: return only the most recent N bars. Omit for full series."
        ),
    ),
    adjust: Literal["qfq", "none"] = Query(
        default="qfq",
        description="qfq forward-adjusts OHLC. none returns raw prices.",
    ),
) -> OhlcvSeriesOut:
    series = get_ohlcv_1d_cache().get(symbol)
    if series is None or len(series) == 0:
        return OhlcvSeriesOut(symbol=symbol, adjust=adjust, bars=[])
    if adjust == "none":
        try:
            bars = get_ohlcv_1d_bars(symbol, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return OhlcvSeriesOut(symbol=symbol, adjust=adjust, bars=bars)

    factors = get_factor_cache().get(symbol)
    if factors is None or factors.times != series.times:
        raise HTTPException(status_code=503, detail=_FACTORS_UNAVAILABLE)
    start = 0 if limit is None else max(0, len(series) - limit)
    opens = forward_adjust(series.open, factors.factor)
    highs = forward_adjust(series.high, factors.factor)
    lows = forward_adjust(series.low, factors.factor)
    closes = forward_adjust(series.close, factors.factor)
    bars = [
        {
            "time": series.times[i],
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": float(series.volume[i]),
        }
        for i in range(start, len(series))
    ]
    return OhlcvSeriesOut(symbol=symbol, adjust=adjust, bars=bars)
