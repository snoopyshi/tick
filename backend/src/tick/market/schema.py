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

# System instrument master (symbol form: 600519.SH / index thscode).
INSTRUMENT_COLUMNS: Final[tuple[str, ...]] = (
    "symbol",
    "ticker",
    "name",
    "exchange",
    "asset_type",
    "currency",
    "list_date",
    "end_date",
    "last_trade_date",
    "last_delivery_date",
    "updated_at",
)

# A-share trading days. No symbol: one row is one session.
TRADING_CALENDAR_COLUMNS: Final[tuple[str, ...]] = (
    "trade_date",
    "vendor",
)

# Cumulative backward-adjust factor aligned to each unadjusted daily bar.
ADJUST_FACTOR_COLUMNS: Final[tuple[str, ...]] = (
    "symbol",
    "trade_date",
    "factor",
    "vendor",
)

# Maps vendor-native codes onto system symbols.
VENDOR_SYMBOL_MAP_COLUMNS: Final[tuple[str, ...]] = (
    "vendor",
    "vendor_symbol",
    "symbol",
    "is_primary",
)

# Fuyao / system asset-type leaves (request filter + instrument.asset_type).
ASSET_TYPES: Final[frozenset[str]] = frozenset(
    {
        "a-share",
        "a-share-index",
        "fund-otc",
        "fund-etf",
        "fund-lof",
        "fund-reits",
        "forex",
        "futures",
        "futures-commodity-index",
        "options",
    }
)

# Default ticker-list ingest covers A-share stocks and indices.
DEFAULT_TICKER_ASSET_TYPES: Final[tuple[str, ...]] = (
    "a-share",
    "a-share-index",
)
