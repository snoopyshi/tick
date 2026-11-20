"""Read canonical market data from research scripts.

Scripts should call this instead of the HTTP API. The files are the same
ones the daily-bar endpoint uses. When a dataset manifest exists, only the
partitions it lists are opened: the pre-migration single file sits in the
same directory and must not be scanned again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.dataset as ds

from tick.core.config import settings
from tick.market.adjust_view import forward_adjust

_COLUMNS = (
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
)
_SCHEMA = pa.schema(
    [
        ("symbol", pa.string()),
        ("trade_date", pa.date32()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("amount", pa.float64()),
    ]
)


class ResearchDataError(RuntimeError):
    """Raised when forward adjustment cannot be computed for a symbol."""


def daily_bars(
    symbol: str,
    *,
    adjust: Literal["qfq", "none"] = "qfq",
) -> pa.Table:
    """Return one symbol's daily bars, oldest first.

    ``qfq`` multiplies open, high, low, and close by the stored backward
    factor and divides by the symbol's last factor. Volume and amount stay
    raw. An unknown symbol is an empty table. Missing or misaligned factors
    raise ``ResearchDataError`` instead of returning raw prices.
    """
    if adjust not in ("qfq", "none"):
        raise ValueError("adjust must be qfq or none")
    bars = _read_bars(symbol)
    if bars.num_rows == 0:
        return _SCHEMA.empty_table()
    bars = bars.sort_by([("trade_date", "ascending")])
    if adjust == "none":
        return bars
    factors = _read_factors(symbol).sort_by([("trade_date", "ascending")])
    if _dates(factors) != _dates(bars):
        raise ResearchDataError("adjust factors unavailable")
    factor_values = [float(value) for value in factors["factor"].to_pylist()]
    return pa.table(
        {
            "symbol": bars["symbol"],
            "trade_date": bars["trade_date"],
            "open": forward_adjust(_floats(bars, "open"), factor_values),
            "high": forward_adjust(_floats(bars, "high"), factor_values),
            "low": forward_adjust(_floats(bars, "low"), factor_values),
            "close": forward_adjust(_floats(bars, "close"), factor_values),
            "volume": bars["volume"],
            "amount": bars["amount"],
        }
    )


def _read_bars(symbol: str) -> pa.Table:
    return _read_symbol(
        _listed_files(
            settings.paths.ohlcv_1d_dataset_manifest,
            settings.paths.ohlcv_1d_partition,
            settings.paths.market_ohlcv_1d,
        ),
        symbol,
        _COLUMNS,
    )


def _read_factors(symbol: str) -> pa.Table:
    return _read_symbol(
        _listed_files(
            settings.paths.adjust_factors_dataset_manifest,
            settings.paths.adjust_factor_partition,
            settings.paths.market_adjust_factors,
        ),
        symbol,
        ("symbol", "trade_date", "factor"),
    )


def _listed_files(manifest_path: Path, partition, single_file: Path) -> list[Path]:
    if manifest_path.is_file():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        dates = sorted(item["trade_date"] for item in payload["partitions"])
        return [partition(trade_date) for trade_date in dates]
    if single_file.is_file():
        return [single_file]
    return []


def _read_symbol(files: list[Path], symbol: str, columns: tuple[str, ...]) -> pa.Table:
    if not files:
        return _SCHEMA.empty_table()
    dataset = ds.dataset([str(path) for path in files], format="parquet")
    return dataset.to_table(filter=ds.field("symbol") == symbol, columns=list(columns))


def _dates(table: pa.Table) -> list[str]:
    if "trade_date" not in table.column_names:
        return []
    return [
        value.isoformat() if hasattr(value, "isoformat") else str(value)
        for value in table["trade_date"].to_pylist()
    ]


def _floats(table: pa.Table, column: str) -> list[float]:
    return [float(value) for value in table[column].to_pylist()]
