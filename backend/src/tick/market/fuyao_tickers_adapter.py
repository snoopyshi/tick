"""Adapt THS ticker-list rows (Fuyao HTTP API) into canonical instruments + map.

Fuyao is the HTTP gateway for Tonghuashun data; system vendor id is always ``ths``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pyarrow as pa

from tick.market.schema import (
    INSTRUMENT_COLUMNS,
    VENDOR_SYMBOL_MAP_COLUMNS,
    VENDOR_THS,
)

_REQUIRED_RAW_COLUMNS = (
    "thscode",
    "ticker",
    "name",
    "exchange",
    "asset_type",
    "currency",
    "list_date",
    "end_date",
    "last_trade_date",
    "last_delivery_date",
)

_RAW_COLUMN_TYPES: dict[str, pa.DataType] = {
    "thscode": pa.string(),
    "ticker": pa.string(),
    "name": pa.string(),
    "exchange": pa.string(),
    "asset_type": pa.string(),
    "currency": pa.string(),
    "list_date": pa.string(),
    "end_date": pa.string(),
    "last_trade_date": pa.string(),
    "last_delivery_date": pa.string(),
    "snapshot_ms": pa.int64(),
}


def fuyao_items_to_raw_table(
    items: list[dict[str, Any]],
    *,
    snapshot_ms: int | None = None,
) -> pa.Table:
    """Build a vendor-shaped Parquet table from Fuyao ``TickerItem`` dicts."""
    columns: dict[str, list[Any]] = {name: [] for name in _RAW_COLUMN_TYPES}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"ticker item must be an object, got {type(item)!r}")
        for key in _REQUIRED_RAW_COLUMNS:
            if key not in item:
                raise ValueError(f"Fuyao ticker item missing field: {key}")
            columns[key].append(item.get(key))
        columns["snapshot_ms"].append(snapshot_ms)

    arrays = {
        name: pa.array(values, type=_RAW_COLUMN_TYPES[name])
        for name, values in columns.items()
    }
    return pa.table(arrays)


def _parse_optional_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return date.fromisoformat(text)
    raise ValueError(f"expected date string or null, got {value!r}")


def _updated_at_from_snapshot(snapshot_ms: object) -> datetime:
    if isinstance(snapshot_ms, int):
        return datetime.fromtimestamp(snapshot_ms / 1000.0, tz=UTC)
    return datetime.now(tz=UTC)


def fuyao_tickers_to_canonical(table: pa.Table) -> tuple[pa.Table, pa.Table]:
    """Map Fuyao raw ticker table → ``(instruments, vendor_symbol_map)``.

    A-share system ``symbol`` equals Fuyao ``thscode`` (e.g. ``600519.SH``).
    """
    missing = [name for name in _REQUIRED_RAW_COLUMNS if name not in table.column_names]
    if missing:
        raise ValueError(f"Fuyao tickers parquet missing columns: {missing}")
    if table.num_rows == 0:
        empty_instruments = pa.table(
            {
                name: pa.array([], type=_instrument_type(name))
                for name in INSTRUMENT_COLUMNS
            }
        )
        empty_map = pa.table(
            {
                name: pa.array([], type=_vendor_map_type(name))
                for name in VENDOR_SYMBOL_MAP_COLUMNS
            }
        )
        return empty_instruments, empty_map

    thscodes = table["thscode"].to_pylist()
    tickers = table["ticker"].to_pylist()
    names = table["name"].to_pylist()
    exchanges = table["exchange"].to_pylist()
    asset_types = table["asset_type"].to_pylist()
    currencies = table["currency"].to_pylist()
    list_dates = [_parse_optional_date(v) for v in table["list_date"].to_pylist()]
    end_dates = [_parse_optional_date(v) for v in table["end_date"].to_pylist()]
    last_trade_dates = [
        _parse_optional_date(v) for v in table["last_trade_date"].to_pylist()
    ]
    last_delivery_dates = [
        _parse_optional_date(v) for v in table["last_delivery_date"].to_pylist()
    ]

    if "snapshot_ms" in table.column_names:
        snapshot_values = table["snapshot_ms"].to_pylist()
    else:
        snapshot_values = [None] * table.num_rows
    updated_ats = [_updated_at_from_snapshot(v) for v in snapshot_values]

    for i, symbol in enumerate(thscodes):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"invalid thscode at row {i}: {symbol!r}")

    instruments = pa.table(
        {
            "symbol": pa.array(thscodes, type=pa.string()),
            "ticker": pa.array(tickers, type=pa.string()),
            "name": pa.array(names, type=pa.string()),
            "exchange": pa.array(exchanges, type=pa.string()),
            "asset_type": pa.array(asset_types, type=pa.string()),
            "currency": pa.array(currencies, type=pa.string()),
            "list_date": pa.array(list_dates, type=pa.date32()),
            "end_date": pa.array(end_dates, type=pa.date32()),
            "last_trade_date": pa.array(last_trade_dates, type=pa.date32()),
            "last_delivery_date": pa.array(last_delivery_dates, type=pa.date32()),
            "updated_at": pa.array(
                updated_ats, type=pa.timestamp("us", tz="UTC")
            ),
        }
    ).select(list(INSTRUMENT_COLUMNS))

    vendor_map = pa.table(
        {
            "vendor": pa.array(
                [VENDOR_THS] * table.num_rows, type=pa.string()
            ),
            "vendor_symbol": pa.array(thscodes, type=pa.string()),
            "symbol": pa.array(thscodes, type=pa.string()),
            "is_primary": pa.array([True] * table.num_rows, type=pa.bool_()),
        }
    ).select(list(VENDOR_SYMBOL_MAP_COLUMNS))

    return instruments, vendor_map


def _instrument_type(name: str) -> pa.DataType:
    if name in {
        "list_date",
        "end_date",
        "last_trade_date",
        "last_delivery_date",
    }:
        return pa.date32()
    if name == "updated_at":
        return pa.timestamp("us", tz="UTC")
    return pa.string()


def _vendor_map_type(name: str) -> pa.DataType:
    if name == "is_primary":
        return pa.bool_()
    return pa.string()
