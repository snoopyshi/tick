"""Convert Fuyao trading-day items into the canonical calendar table."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa

from tick.market.schema import TRADING_CALENDAR_COLUMNS, VENDOR_THS

SHANGHAI = ZoneInfo("Asia/Shanghai")

RAW_CALENDAR_COLUMNS: tuple[str, ...] = ("date_ms", "date", "snapshot_ms")


def shanghai_midnight_ms(day: date) -> int:
    """Unix milliseconds of ``day`` at 00:00 in Asia/Shanghai."""
    moment = datetime(day.year, day.month, day.day, tzinfo=SHANGHAI)
    return int(moment.timestamp() * 1000)


def trading_days_to_raw(
    items: list[dict[str, Any]],
    *,
    snapshot_ms: int | None,
) -> pa.Table:
    """Keep the vendor fields. ``date`` stays ``yyyyMMdd``."""
    return pa.table(
        {
            "date_ms": pa.array(
                [_required_int(item, "date_ms") for item in items],
                type=pa.int64(),
            ),
            "date": pa.array(
                [_required_str(item, "date") for item in items],
                type=pa.string(),
            ),
            "snapshot_ms": pa.array(
                [snapshot_ms] * len(items),
                type=pa.int64(),
            ),
        }
    ).select(list(RAW_CALENDAR_COLUMNS))


def trading_days_to_canonical(table: pa.Table) -> pa.Table:
    """One row per A-share session, ordered by ``trade_date``.

    ``date_ms`` must be that date's Shanghai midnight. A mismatched stamp
    means the vendor date and the instant do not describe the same session.
    """
    rows: list[tuple[date, int]] = []
    for date_ms, raw_date in zip(
        table["date_ms"].to_pylist(),
        table["date"].to_pylist(),
        strict=True,
    ):
        day = _parse_yyyymmdd(raw_date)
        if date_ms != shanghai_midnight_ms(day):
            raise ValueError(
                f"date_ms {date_ms} does not match Shanghai midnight of {raw_date}"
            )
        rows.append((day, date_ms))
    rows.sort(key=lambda item: item[0])
    trade_dates = [item[0] for item in rows]
    if len(trade_dates) != len(set(trade_dates)):
        raise ValueError("duplicate trade_date")
    return pa.table(
        {
            "trade_date": pa.array(trade_dates, type=pa.date32()),
            "vendor": pa.array([VENDOR_THS] * len(trade_dates), type=pa.string()),
        }
    ).select(list(TRADING_CALENDAR_COLUMNS))


def _parse_yyyymmdd(value: object) -> date:
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        raise ValueError(f"date must be yyyyMMdd, got {value!r}")
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError as exc:
        raise ValueError(f"date must be yyyyMMdd, got {value!r}") from exc


def _required_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer, got {value!r}")
    return value


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a string, got {value!r}")
    return value
