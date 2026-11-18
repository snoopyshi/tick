"""Canonical market data definitions used by strategies and backtests."""

from typing import Final

VENDOR_THS: Final = "ths"

# Daily OHLCV column order for system-standard Parquet files.
OHLCV_1D_COLUMNS: Final[tuple[str, ...]] = (
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adjust",
    "vendor",
    "currency",
)

# Corporate-action / ex-date events (used to derive adjust factors).
CORP_ACTION_COLUMNS: Final[tuple[str, ...]] = (
    "symbol",
    "ex_date",
    "dividend_per_share",
    "bonus_per_share",
    "allotment_ratio",
    "allotment_price",
    "vendor",
    "currency",
)
