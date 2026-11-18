"""In-process cache for canonical daily OHLCV bars, keyed by symbol."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from tick.core.config import settings

logger = logging.getLogger(__name__)

_OHLCV_COLUMNS = (
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
)


@dataclass(slots=True)
class OhlcvSeries:
    """One symbol's daily bars, sorted by ``times`` ascending."""

    times: list[str]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    amount: list[float]

    def __len__(self) -> int:
        return len(self.times)


_ohlcv_1d: dict[str, OhlcvSeries] = {}


def get_ohlcv_1d_cache() -> dict[str, OhlcvSeries]:
    return _ohlcv_1d


def clear_ohlcv_1d_cache() -> None:
    _ohlcv_1d.clear()


def load_ohlcv_1d_into_memory(path: Path | None = None) -> dict[str, OhlcvSeries]:
    """Load canonical daily OHLCV parquet into ``symbol -> OhlcvSeries``."""
    source = path or settings.paths.market_ohlcv_1d
    clear_ohlcv_1d_cache()

    if not source.is_file():
        logger.warning("ohlcv cache skipped: file not found: %s", source)
        return _ohlcv_1d

    started = time.perf_counter()
    logger.info("loading ohlcv 1d cache from %s", source)
    table = pq.read_table(source, columns=list(_OHLCV_COLUMNS))
    table = table.sort_by(
        [("symbol", "ascending"), ("trade_date", "ascending")],
    )

    symbols = table["symbol"].to_pylist()
    times = [
        value.isoformat() if hasattr(value, "isoformat") else str(value)
        for value in table["trade_date"].to_pylist()
    ]
    opens = table["open"].to_pylist()
    highs = table["high"].to_pylist()
    lows = table["low"].to_pylist()
    closes = table["close"].to_pylist()
    volumes = table["volume"].to_pylist()
    amounts = table["amount"].to_pylist()

    n = table.num_rows
    i = 0
    while i < n:
        symbol = symbols[i]
        j = i + 1
        while j < n and symbols[j] == symbol:
            j += 1
        _ohlcv_1d[symbol] = OhlcvSeries(
            times=times[i:j],
            open=opens[i:j],
            high=highs[i:j],
            low=lows[i:j],
            close=closes[i:j],
            volume=volumes[i:j],
            amount=amounts[i:j],
        )
        i = j

    elapsed = time.perf_counter() - started
    logger.info(
        "ohlcv 1d cache ready: symbols=%s bars=%s elapsed=%.2fs",
        len(_ohlcv_1d),
        n,
        elapsed,
    )
    return _ohlcv_1d
