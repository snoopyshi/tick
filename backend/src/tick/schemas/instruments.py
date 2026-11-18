from datetime import date, datetime

from pydantic import BaseModel, Field


class InstrumentOut(BaseModel):
    symbol: str
    ticker: str
    name: str
    exchange: str | None = None
    asset_type: str
    currency: str
    list_date: date | None = None
    end_date: date | None = None
    last_trade_date: date | None = None
    last_delivery_date: date | None = None
    updated_at: datetime | None = None


class InstrumentListResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[InstrumentOut]
