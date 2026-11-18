"""Adapt Tonghuashun corporate-action events into the canonical schema."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc

from tick.market.schema import CORP_ACTION_COLUMNS, VENDOR_THS

_REQUIRED_RAW_COLUMNS = (
    "thscode",
    "ex_date_ms",
    "dividend_per_share",
    "per_share_bonus",
    "allotment_ratio",
    "allotment_price",
    "currency",
)


def ths_corp_actions_to_canonical(table: pa.Table) -> pa.Table:
    """Map THS ex-date event rows to the system corporate-action schema."""
    missing = [name for name in _REQUIRED_RAW_COLUMNS if name not in table.column_names]
    if missing:
        raise ValueError(f"THS corp-actions parquet missing columns: {missing}")

    ex_ts = pc.cast(table["ex_date_ms"], pa.timestamp("ms", tz="UTC"))
    ex_local = pc.cast(ex_ts, pa.timestamp("ms", tz="Asia/Shanghai"))
    ex_date = pc.cast(ex_local, pa.date32())

    out = pa.table(
        {
            "symbol": table["thscode"],
            "ex_date": ex_date,
            "dividend_per_share": table["dividend_per_share"],
            "bonus_per_share": table["per_share_bonus"],
            "allotment_ratio": table["allotment_ratio"],
            "allotment_price": table["allotment_price"],
            "vendor": pa.repeat(
                pa.scalar(VENDOR_THS, type=pa.string()),
                table.num_rows,
            ),
            "currency": table["currency"],
        }
    )
    return out.select(list(CORP_ACTION_COLUMNS))
