"""Derive daily backward-adjust factors from unadjusted bars and ex-date events."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import pyarrow as pa

from tick.market.schema import ADJUST_FACTOR_COLUMNS, VENDOR_THS


class AdjustFactorError(ValueError):
    """Raised when an in-window event cannot produce a positive ratio."""


@dataclass(frozen=True, slots=True)
class AdjustFactorResult:
    table: pa.Table
    events_applied: int
    events_before_window: int
    events_after_window: int
    events_zero: int
    events_no_bars: int


def compute_adjust_factors(bars: pa.Table, events: pa.Table) -> AdjustFactorResult:
    """Return one factor per bar. Prices themselves are not modified."""
    grouped = _group_bars(bars)
    counts = {
        "events_applied": 0,
        "events_before_window": 0,
        "events_after_window": 0,
        "events_zero": 0,
        "events_no_bars": 0,
    }
    applied: dict[str, dict[date, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for row in events.to_pylist():
        symbol = row["symbol"]
        series = grouped.get(symbol)
        if series is None:
            counts["events_no_bars"] += 1
            continue
        ex_date = row["ex_date"]
        first = series[0][0]
        last = series[-1][0]
        if ex_date <= first:
            counts["events_before_window"] += 1
            continue
        if ex_date > last:
            counts["events_after_window"] += 1
            continue
        dividend = float(row["dividend_per_share"])
        bonus = float(row["bonus_per_share"])
        allotment_ratio = float(row["allotment_ratio"])
        if dividend == 0.0 and bonus == 0.0 and allotment_ratio == 0.0:
            counts["events_zero"] += 1
            continue
        counts["events_applied"] += 1
        applied[symbol][ex_date].append(
            {
                "dividend": dividend,
                "bonus": bonus,
                "allotment_ratio": allotment_ratio,
                "allotment_price": float(row["allotment_price"]),
            }
        )

    symbols: list[str] = []
    trade_dates: list[date] = []
    factors: list[float] = []
    for symbol in sorted(grouped):
        series = grouped[symbol]
        merged = [
            (ex_date, _merge_same_day(rows))
            for ex_date, rows in sorted(applied.get(symbol, {}).items())
        ]
        symbol_factors = _factors_for_symbol(symbol, series, merged)
        for (trade_date, _close), factor in zip(series, symbol_factors, strict=True):
            symbols.append(symbol)
            trade_dates.append(trade_date)
            factors.append(factor)

    table = pa.table(
        {
            "symbol": pa.array(symbols, type=pa.string()),
            "trade_date": pa.array(trade_dates, type=pa.date32()),
            "factor": pa.array(factors, type=pa.float64()),
            "vendor": pa.array([VENDOR_THS] * len(symbols), type=pa.string()),
        }
    ).select(list(ADJUST_FACTOR_COLUMNS))
    return AdjustFactorResult(table=table, **counts)


def _group_bars(bars: pa.Table) -> dict[str, list[tuple[date, float]]]:
    rows = bars.select(["symbol", "trade_date", "close"]).to_pylist()
    rows.sort(key=lambda row: (row["symbol"], row["trade_date"]))
    grouped: dict[str, list[tuple[date, float]]] = {}
    for row in rows:
        grouped.setdefault(row["symbol"], []).append(
            (row["trade_date"], float(row["close"]))
        )
    return grouped


def _merge_same_day(rows: list[dict]) -> dict[str, float]:
    unique: list[dict] = []
    seen: set[tuple[float, float, float, float]] = set()
    for row in rows:
        key = (
            row["dividend"],
            row["bonus"],
            row["allotment_ratio"],
            row["allotment_price"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    allotment_ratio = sum(row["allotment_ratio"] for row in unique)
    if allotment_ratio == 0.0:
        allotment_price = 0.0
    else:
        weighted = sum(
            row["allotment_price"] * row["allotment_ratio"] for row in unique
        )
        allotment_price = weighted / allotment_ratio
    return {
        "dividend": sum(row["dividend"] for row in unique),
        "bonus": sum(row["bonus"] for row in unique),
        "allotment_ratio": allotment_ratio,
        "allotment_price": allotment_price,
    }


def _factors_for_symbol(
    symbol: str,
    series: list[tuple[date, float]],
    events: list[tuple[date, dict[str, float]]],
) -> list[float]:
    factors: list[float] = []
    current = 1.0
    event_index = 0
    dates = [item[0] for item in series]
    closes = [item[1] for item in series]
    for index, trade_date in enumerate(dates):
        while event_index < len(events) and events[event_index][0] <= trade_date:
            ex_date, terms = events[event_index]
            if index == 0 or dates[index - 1] >= ex_date:
                raise AdjustFactorError(
                    f"{symbol} {ex_date.isoformat()} has no previous bar"
                )
            ratio = _ratio(closes[index - 1], terms)
            current = current / ratio
            event_index += 1
        factors.append(current)
    return factors


def advance_factors(
    *,
    dates: list[date],
    closes_by_date: dict[date, dict[str, float]],
    seed_factors: dict[str, float],
    seed_closes: dict[str, float],
    events: list[dict],
) -> dict[date, dict[str, float]]:
    """Carry factors across ``dates`` without rereading older history.

    ``seed_factors`` and ``seed_closes`` are the last partition strictly before
    the first date. Symbols absent from the seed start at factor 1 on their
    first bar. An event on that first bar does not change the factor.
    """
    grouped: dict[date, list[dict]] = defaultdict(list)
    for row in events:
        grouped[row["ex_date"]].append(row)

    factors = dict(seed_factors)
    prev_closes = dict(seed_closes)
    written: dict[date, dict[str, float]] = {}
    for trade_date in dates:
        day_closes = closes_by_date.get(trade_date, {})
        for symbol, terms in _events_by_symbol(grouped.get(trade_date, [])):
            is_new = symbol not in factors and symbol not in prev_closes
            if is_new:
                continue
            if symbol not in prev_closes:
                raise AdjustFactorError(
                    f"{symbol} {trade_date.isoformat()} has no previous bar"
                )
            factors[symbol] = factors.get(symbol, 1.0) / _ratio(
                prev_closes[symbol], terms
            )
        day_factors: dict[str, float] = {}
        for symbol, close in day_closes.items():
            if symbol not in factors:
                factors[symbol] = 1.0
            day_factors[symbol] = factors[symbol]
            prev_closes[symbol] = close
        written[trade_date] = day_factors
    return written


def _events_by_symbol(rows: list[dict]) -> list[tuple[str, dict[str, float]]]:
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(
            {
                "dividend": float(row["dividend_per_share"]),
                "bonus": float(row["bonus_per_share"]),
                "allotment_ratio": float(row["allotment_ratio"]),
                "allotment_price": float(row["allotment_price"]),
            }
        )
    merged: list[tuple[str, dict[str, float]]] = []
    for symbol, items in by_symbol.items():
        terms = _merge_same_day(items)
        if (
            terms["dividend"] == 0.0
            and terms["bonus"] == 0.0
            and terms["allotment_ratio"] == 0.0
        ):
            continue
        merged.append((symbol, terms))
    return merged


def _ratio(prev_close: float, terms: dict[str, float]) -> float:
    dividend = terms["dividend"]
    bonus = terms["bonus"]
    allotment_ratio = terms["allotment_ratio"]
    allotment_price = terms["allotment_price"]
    denominator = 1.0 + bonus + allotment_ratio
    if prev_close <= 0 or denominator <= 0:
        raise AdjustFactorError("adjustment denominator is not positive")
    ex_close = (
        prev_close - dividend + allotment_price * allotment_ratio
    ) / denominator
    if ex_close <= 0:
        raise AdjustFactorError("ex-rights reference price is not positive")
    return ex_close / prev_close
