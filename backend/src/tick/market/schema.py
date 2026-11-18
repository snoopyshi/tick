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
