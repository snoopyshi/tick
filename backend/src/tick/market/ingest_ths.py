"""Ingest Tonghuashun raw daily OHLCV into the canonical market store."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pyarrow.parquet as pq

from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.market.manifest import (
    count_symbols,
    min_max_date,
    produced_at_now,
    publish_parquet_with_manifest,
    require_adjust_none,
    require_unique_keys,
)
from tick.market.schema import OHLCV_1D_COLUMNS, VENDOR_THS
from tick.market.ths_adapter import ths_daily_to_canonical

logger = logging.getLogger(__name__)


def ingest_ths_daily(
    *,
    raw_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    paths = settings.paths
    paths.ensure()

    source = raw_path or paths.raw_ths_ohlcv_1d
    target = output_path or paths.market_ohlcv_1d
    if not source.is_file():
        raise FileNotFoundError(f"THS raw daily parquet not found: {source}")

    logger.info("reading THS raw daily bars from %s", source)
    raw = pq.read_table(source)
    logger.info("raw rows=%s cols=%s", raw.num_rows, raw.column_names)

    canonical = ths_daily_to_canonical(raw)
    require_adjust_none(canonical)
    require_unique_keys(canonical, ("symbol", "trade_date"))
    logger.info(
        "canonical rows=%s writing %s",
        canonical.num_rows,
        target,
    )
    low, high = min_max_date(canonical, "trade_date")
    manifest: dict = {
        "capability_id": "market.ohlcv.1d",
        "schema_version": 1,
        "columns": list(OHLCV_1D_COLUMNS),
        "rows": canonical.num_rows,
        "symbols": count_symbols(canonical),
        "vendor": VENDOR_THS,
        "snapshot_id": source.stem,
        "produced_at": produced_at_now(),
        "adjust": "none",
    }
    if low is not None and high is not None:
        manifest["min_date"] = low
        manifest["max_date"] = high
    publish_parquet_with_manifest(canonical, target, manifest)

    logger.info("ingest done: %s (%s rows)", target, canonical.num_rows)
    return target


def main() -> None:
    configure_tick_logging()
    parser = argparse.ArgumentParser(
        description="Convert THS raw daily OHLCV parquet into canonical market data.",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=None,
        help="Raw THS parquet path (default: DATA_DIR/raw/ths/ohlcv/1d/...)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Canonical output path "
            "(default: DATA_DIR/market/ohlcv/1d/a_share_daily_k_1d.parquet)"
        ),
    )
    args = parser.parse_args()
    ingest_ths_daily(raw_path=args.raw, output_path=args.output)


if __name__ == "__main__":
    main()
