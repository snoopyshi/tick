from typing import Literal

from pydantic import BaseModel, Field


class OhlcvBarOut(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class OhlcvSeriesOut(BaseModel):
    symbol: str
    adjust: Literal["qfq", "none"]
    bars: list[OhlcvBarOut] = Field(default_factory=list)
