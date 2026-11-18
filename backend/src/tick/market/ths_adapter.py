"""Adapt Tonghuashun (同花顺) daily OHLCV into the canonical schema."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc

from tick.market.schema import OHLCV_1D_COLUMNS, VENDOR_THS

_REQUIRED_RAW_COLUMNS = (
    "thscode",
    "currency",
    "adjusted",
    "date_ms",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "turnover",
)


def ths_daily_to_canonical(table: pa.Table) -> pa.Table:
    """Map a THS daily bar table to the system OHLCV_1D schema."""
    missing = [name for name in _REQUIRED_RAW_COLUMNS if name not in table.column_names]
    if missing:
        raise ValueError(f"THS daily parquet missing columns: {missing}")

    # THS date_ms is UTC ms that corresponds to Asia/Shanghai midnight.
    trade_ts = pc.cast(table["date_ms"], pa.timestamp("ms", tz="UTC"))
    trade_local = pc.cast(trade_ts, pa.timestamp("ms", tz="Asia/Shanghai"))
    trade_date = pc.cast(trade_local, pa.date32())

    out = pa.table(
        {
            "symbol": table["thscode"],
            "trade_date": trade_date,
            "open": table["open_price"],
            "high": table["high_price"],
            "low": table["low_price"],
            "close": table["close_price"],
            "volume": table["volume"],
            "amount": table["turnover"],
            "adjust": table["adjusted"],
            "vendor": pa.repeat(
                pa.scalar(VENDOR_THS, type=pa.string()),
                table.num_rows,
            ),
            "currency": table["currency"],
        }
    )
    return out.select(list(OHLCV_1D_COLUMNS))
