"""In-process cache for backward-adjust factors, keyed by symbol.

The cache is cleared when the file is missing so a later forward-adjust
request cannot keep using factors loaded from a previous file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings

logger = logging.getLogger(__name__)

_FACTOR_COLUMNS = ("symbol", "trade_date", "factor")


@dataclass(slots=True)
class FactorSeries:
    """One symbol's factors, sorted by ``times`` ascending."""

    times: list[str]
    factor: list[float]


_factors: dict[str, FactorSeries] = {}


def get_factor_cache() -> dict[str, FactorSeries]:
    return _factors


def clear_factor_cache() -> None:
    _factors.clear()


def load_adjust_factors_into_memory(
    path: Path | None = None,
) -> dict[str, FactorSeries]:
    """Load factors into ``symbol -> FactorSeries``.

    When the caller does not pass ``path`` and a trade-date dataset manifest
    exists, partitions are concatenated. An explicit ``path`` still reads one file.
    """
    if path is None and settings.paths.adjust_factors_dataset_manifest.is_file():
        return _load_partitioned_factors()
    source = path or settings.paths.market_adjust_factors
    clear_factor_cache()
    if not source.is_file():
        logger.warning("factor cache skipped: file not found: %s", source)
        return _factors
    table = pq.read_table(source, columns=list(_FACTOR_COLUMNS))
    table = table.sort_by(
        [("symbol", "ascending"), ("trade_date", "ascending")],
    )
    _fill_cache(table)
    return _factors


def _load_partitioned_factors() -> dict[str, FactorSeries]:
    clear_factor_cache()
    manifest_path = settings.paths.adjust_factors_dataset_manifest
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    dates = sorted(item["trade_date"] for item in payload["partitions"])
    if not dates:
        return _factors
    tables = [
        pq.read_table(
            settings.paths.adjust_factor_partition(trade_date),
            columns=list(_FACTOR_COLUMNS),
        )
        for trade_date in dates
    ]
    table = pa.concat_tables(tables).sort_by(
        [("symbol", "ascending"), ("trade_date", "ascending")],
    )
    _fill_cache(table)
    return _factors


def _fill_cache(table: pa.Table) -> None:
    symbols = table["symbol"].to_pylist()
    times = [
        value.isoformat() if hasattr(value, "isoformat") else str(value)
        for value in table["trade_date"].to_pylist()
    ]
    factors = table["factor"].to_pylist()
    n = table.num_rows
    i = 0
    while i < n:
        symbol = symbols[i]
        j = i + 1
        while j < n and symbols[j] == symbol:
            j += 1
        _factors[symbol] = FactorSeries(times=times[i:j], factor=factors[i:j])
        i = j
