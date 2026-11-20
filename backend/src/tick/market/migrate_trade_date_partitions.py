"""Split the single-file daily bars and factors into trade-date partitions."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.market.manifest import count_symbols, produced_at_now
from tick.market.partitions import trade_date_partition
from tick.market.schema import ADJUST_FACTOR_COLUMNS, OHLCV_1D_COLUMNS

logger = logging.getLogger(__name__)


def migrate_trade_date_partitions() -> None:
    """Write dataset manifests. The original single files are left in place.

    The registry prefers the dataset manifest once it exists. Re-running
    overwrites the partitions and the manifest.
    """
    paths = settings.paths
    paths.ensure()
    if not paths.market_ohlcv_1d.is_file():
        raise FileNotFoundError(
            f"single-file daily bars not found: {paths.market_ohlcv_1d}"
        )
    bars = pq.read_table(paths.market_ohlcv_1d)
    _write_dates(
        bars,
        date_column="trade_date",
        dataset_dir=paths.market_ohlcv_1d_dir,
        manifest_path=paths.ohlcv_1d_dataset_manifest,
        capability_id="market.ohlcv.1d",
        columns=OHLCV_1D_COLUMNS,
        adjust="none",
    )
    if paths.market_adjust_factors.is_file():
        factors = pq.read_table(paths.market_adjust_factors)
        _write_dates(
            factors,
            date_column="trade_date",
            dataset_dir=paths.market_adjust_factors_dir,
            manifest_path=paths.adjust_factors_dataset_manifest,
            capability_id="market.adjust_factors",
            columns=ADJUST_FACTOR_COLUMNS,
            adjust=None,
        )
    logger.info("trade-date migration wrote dataset manifests")


def _write_dates(
    table: pa.Table,
    *,
    date_column: str,
    dataset_dir,
    manifest_path,
    capability_id: str,
    columns: tuple[str, ...],
    adjust: str | None,
) -> None:
    rows = table.select(list(columns)).to_pylist()
    grouped: dict[date, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[date_column], []).append(row)
    entries = []
    for trade_date in sorted(grouped):
        day_rows = sorted(grouped[trade_date], key=lambda item: item["symbol"])
        target = trade_date_partition(dataset_dir, trade_date.isoformat())
        target.parent.mkdir(parents=True, exist_ok=True)
        day = pa.table(
            {name: [row[name] for row in day_rows] for name in columns}
        ).select(list(columns))
        pq.write_table(day, target, compression="zstd")
        entries.append(
            {
                "trade_date": trade_date.isoformat(),
                "rows": day.num_rows,
                "bytes": target.stat().st_size,
            }
        )
    from tick.market.partitions import build_dataset_manifest

    watermark = entries[-1]["trade_date"]
    symbols = count_symbols(
        pq.read_table(trade_date_partition(dataset_dir, watermark))
    )
    payload = build_dataset_manifest(
        capability_id=capability_id,
        columns=columns,
        partitions=entries,
        symbols=symbols,
        snapshot_id=f"migrated:{produced_at_now()}",
        batch_dates=[item["trade_date"] for item in entries],
        adjust=adjust,
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    configure_tick_logging()
    argparse.ArgumentParser(
        description="Split single-file daily bars and factors into trade dates.",
    ).parse_args()
    migrate_trade_date_partitions()


if __name__ == "__main__":
    main()
