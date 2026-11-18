"""In-process cache for canonical instruments, keyed by symbol."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pyarrow.parquet as pq

from tick.core.config import settings
from tick.market.schema import INSTRUMENT_COLUMNS

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class Instrument:
    """One system instrument from the canonical master table."""

    symbol: str
    ticker: str
    name: str
    exchange: str | None
    asset_type: str
    currency: str
    list_date: date | None
    end_date: date | None
    last_trade_date: date | None
    last_delivery_date: date | None
    updated_at: datetime | None


_instruments: dict[str, Instrument] = {}


def get_instruments_cache() -> dict[str, Instrument]:
    return _instruments


def clear_instruments_cache() -> None:
    _instruments.clear()


def list_instruments(
    *,
    q: str | None = None,
    asset_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Instrument], int]:
    """Filter in-memory instruments; return ``(page_items, total)``.

    Empty ``asset_types`` means no asset-type filter (all types).
    ``q`` matches ``symbol`` / ``ticker`` / ``name`` case-insensitively.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    query = (q or "").strip().casefold()
    allowed_types = {value for value in (asset_types or []) if value}

    matched: list[Instrument] = []
    for instrument in _instruments.values():
        if allowed_types and instrument.asset_type not in allowed_types:
            continue
        if query:
            haystacks = (
                instrument.symbol.casefold(),
                instrument.ticker.casefold(),
                instrument.name.casefold(),
            )
            if not any(query in text for text in haystacks):
                continue
        matched.append(instrument)

    matched.sort(key=lambda item: item.symbol)
    total = len(matched)
    return matched[offset : offset + limit], total


def load_instruments_into_memory(path: Path | None = None) -> dict[str, Instrument]:
    """Load canonical instruments parquet into ``symbol -> Instrument``."""
    source = path or settings.paths.market_instruments
    clear_instruments_cache()

    if not source.is_file():
        logger.warning("instruments cache skipped: file not found: %s", source)
        return _instruments

    started = time.perf_counter()
    logger.info("loading instruments cache from %s", source)
    table = pq.read_table(source, columns=list(INSTRUMENT_COLUMNS))

    rows = table.to_pylist()
    for row in rows:
        symbol = row["symbol"]
        if not isinstance(symbol, str) or not symbol:
            continue
        _instruments[symbol] = Instrument(
            symbol=symbol,
            ticker=row["ticker"] or "",
            name=row["name"] or "",
            exchange=row["exchange"],
            asset_type=row["asset_type"] or "",
            currency=row["currency"] or "",
            list_date=row["list_date"],
            end_date=row["end_date"],
            last_trade_date=row["last_trade_date"],
            last_delivery_date=row["last_delivery_date"],
            updated_at=row["updated_at"],
        )

    elapsed = time.perf_counter() - started
    logger.info(
        "instruments cache ready: symbols=%s elapsed=%.2fs",
        len(_instruments),
        elapsed,
    )
    return _instruments
