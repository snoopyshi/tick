"""Replace one batch of trade-date partitions for daily bars and factors."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.market.adjust_factors import AdjustFactorError, advance_factors
from tick.market.catalog import get_capability
from tick.market.ingest_adjust_factors import DependencyNotReadyError
from tick.market.manifest import count_symbols, require_adjust_none, require_unique_keys
from tick.market.partitions import (
    build_dataset_manifest,
    dataset_snapshot_id,
    load_dataset_manifest,
    merge_partitions,
    publish_tables,
)
from tick.market.schema import ADJUST_FACTOR_COLUMNS, OHLCV_1D_COLUMNS, VENDOR_THS

logger = logging.getLogger(__name__)


class SingleFileLayoutError(RuntimeError):
    """Raised when daily bars are still one file and have not been migrated."""


def ingest_trade_date_batch(bars: pa.Table) -> list[date]:
    """Write only the trade dates present in ``bars``.

    Factor partitions outside the affected range are left untouched. Corp
    actions must already be ``ready``. A single-file daily store must be
    migrated before the first batch.
    """
    paths = settings.paths
    paths.ensure()
    if (
        paths.market_ohlcv_1d.is_file()
        and not paths.ohlcv_1d_dataset_manifest.is_file()
    ):
        raise SingleFileLayoutError(
            "daily bars are still a single parquet; "
            "run tick-migrate-trade-date-partitions first"
        )
    events_view = get_capability("market.corp_actions")
    if events_view is None or events_view.status != "ready":
        blocked = [events_view] if events_view is not None else []
        raise DependencyNotReadyError(blocked)

    require_adjust_none(bars)
    require_unique_keys(bars, ("symbol", "trade_date"))
    bars = bars.select(list(OHLCV_1D_COLUMNS))
    by_date = _bars_by_date(bars)
    batch_dates = sorted(by_date)
    if not batch_dates:
        raise ValueError("batch has no bars")

    ohlcv_manifest = load_dataset_manifest(paths.ohlcv_1d_dataset_manifest)
    factor_manifest = load_dataset_manifest(paths.adjust_factors_dataset_manifest)
    existing_dates = _partition_dates(ohlcv_manifest.data)
    events = pq.read_table(paths.market_corp_actions).to_pylist()
    write_dates = _factor_dates(batch_dates, existing_dates, events)

    closes = {item: _closes_from_rows(rows) for item, rows in by_date.items()}
    for item in write_dates:
        if item not in closes:
            closes[item] = _read_closes(paths.ohlcv_1d_partition(item.isoformat()))
    seed_date = _seed_date(write_dates[0], existing_dates)
    seed_closes: dict[str, float] = {}
    seed_factors: dict[str, float] = {}
    if seed_date is not None:
        seed_closes = _read_closes(paths.ohlcv_1d_partition(seed_date.isoformat()))
        factor_path = paths.adjust_factor_partition(seed_date.isoformat())
        if factor_path.is_file():
            seed_factors = _read_factors(factor_path)

    factor_maps = advance_factors(
        dates=write_dates,
        closes_by_date=closes,
        seed_factors=seed_factors,
        seed_closes=seed_closes,
        events=events,
    )

    files: list[tuple[Path, pa.Table]] = []
    ohlcv_updates: dict[str, dict[str, int]] = {}
    factor_updates: dict[str, dict[str, int]] = {}
    for item in batch_dates:
        key = item.isoformat()
        table = _table_for_date(by_date[item])
        files.append((paths.ohlcv_1d_partition(key), table))
        ohlcv_updates[key] = {"rows": table.num_rows, "bytes": 0}
    for item in write_dates:
        key = item.isoformat()
        table = _factor_table(item, factor_maps[item])
        files.append((paths.adjust_factor_partition(key), table))
        factor_updates[key] = {"rows": table.num_rows, "bytes": 0}

    snapshot = dataset_snapshot_id([item.isoformat() for item in batch_dates])
    ohlcv_existing = _partition_entries(ohlcv_manifest.data)
    factor_existing = _partition_entries(factor_manifest.data)

    def manifests(sizes: dict[Path, int]) -> list[tuple[Path, dict]]:
        _fill_bytes(ohlcv_updates, paths.ohlcv_1d_partition, sizes)
        _fill_bytes(factor_updates, paths.adjust_factor_partition, sizes)
        ohlcv_parts = merge_partitions(ohlcv_existing, ohlcv_updates)
        factor_parts = merge_partitions(factor_existing, factor_updates)
        watermark_key = ohlcv_parts[-1]["trade_date"]
        symbols = count_symbols(_read_table(paths.ohlcv_1d_partition(watermark_key)))
        batch_keys = [item.isoformat() for item in batch_dates]
        return [
            (
                paths.ohlcv_1d_dataset_manifest,
                build_dataset_manifest(
                    capability_id="market.ohlcv.1d",
                    columns=OHLCV_1D_COLUMNS,
                    partitions=ohlcv_parts,
                    symbols=symbols,
                    snapshot_id=snapshot,
                    batch_dates=batch_keys,
                    adjust="none",
                ),
            ),
            (
                paths.adjust_factors_dataset_manifest,
                build_dataset_manifest(
                    capability_id="market.adjust_factors",
                    columns=ADJUST_FACTOR_COLUMNS,
                    partitions=factor_parts,
                    symbols=count_symbols(
                        _read_table(paths.adjust_factor_partition(watermark_key))
                    ),
                    snapshot_id=snapshot,
                    batch_dates=batch_keys,
                ),
            ),
        ]

    publish_tables(files, manifests)
    logger.info("trade-date batch written: %s", snapshot)
    return batch_dates


def _bars_by_date(bars: pa.Table) -> dict[date, list[dict]]:
    grouped: dict[date, list[dict]] = {}
    for row in bars.to_pylist():
        grouped.setdefault(row["trade_date"], []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["symbol"])
    return grouped


def _partition_dates(data: dict | None) -> list[date]:
    if not data:
        return []
    return sorted(date.fromisoformat(item["trade_date"]) for item in data["partitions"])


def _partition_entries(data: dict | None) -> list[dict]:
    if not data:
        return []
    return list(data["partitions"])


def _factor_dates(
    batch_dates: list[date],
    existing: list[date],
    events: list[dict],
) -> list[date]:
    watermark = existing[-1] if existing else None
    batch_set = set(batch_dates)
    event_dates = sorted(
        {
            row["ex_date"]
            for row in events
            if row["ex_date"] in batch_set
            and not (
                float(row["dividend_per_share"]) == 0.0
                and float(row["bonus_per_share"]) == 0.0
                and float(row["allotment_ratio"]) == 0.0
            )
        }
    )
    pure_tail = watermark is None or batch_dates[0] > watermark
    if pure_tail or not event_dates:
        return batch_dates
    start = event_dates[0]
    end = max(watermark, batch_dates[-1])
    covered = {item for item in existing if start <= item <= end}
    covered.update(item for item in batch_dates if start <= item <= end)
    return sorted(covered)


def _seed_date(first: date, existing: list[date]) -> date | None:
    earlier = [item for item in existing if item < first]
    if not earlier:
        return None
    return earlier[-1]


def _closes_from_rows(rows: list[dict]) -> dict[str, float]:
    return {row["symbol"]: float(row["close"]) for row in rows}


def _read_closes(path: Path) -> dict[str, float]:
    table = pq.read_table(path, columns=["symbol", "close"])
    symbols = table["symbol"].to_pylist()
    closes = table["close"].to_pylist()
    return dict(zip(symbols, closes, strict=True))


def _read_factors(path: Path) -> dict[str, float]:
    table = pq.read_table(path, columns=["symbol", "factor"])
    return dict(
        zip(table["symbol"].to_pylist(), table["factor"].to_pylist(), strict=True)
    )


def _read_table(path: Path) -> pa.Table:
    return pq.read_table(path)


def _table_for_date(rows: list[dict]) -> pa.Table:
    columns = {name: [row[name] for row in rows] for name in OHLCV_1D_COLUMNS}
    columns["vendor"] = [VENDOR_THS] * len(rows)
    return pa.table(columns).select(list(OHLCV_1D_COLUMNS))


def _factor_table(trade_date: date, factors: dict[str, float]) -> pa.Table:
    symbols = sorted(factors)
    return pa.table(
        {
            "symbol": symbols,
            "trade_date": [trade_date] * len(symbols),
            "factor": [factors[symbol] for symbol in symbols],
            "vendor": [VENDOR_THS] * len(symbols),
        }
    ).select(list(ADJUST_FACTOR_COLUMNS))


def _fill_bytes(
    updates: dict[str, dict[str, int]],
    path_for,
    sizes: dict[Path, int],
) -> None:
    for trade_date, values in updates.items():
        values["bytes"] = sizes[path_for(trade_date)]


def main() -> None:
    configure_tick_logging()
    parser = argparse.ArgumentParser(
        description="Replace a batch of daily-bar trade dates and their factors.",
    )
    parser.add_argument(
        "--bars",
        type=Path,
        required=True,
        help="Canonical unadjusted bars for the dates in this batch",
    )
    args = parser.parse_args()
    try:
        ingest_trade_date_batch(pq.read_table(args.bars))
    except DependencyNotReadyError as exc:
        for view in exc.views:
            print(
                f"{view.id} status={view.status} issues={list(view.issues)}",
                file=sys.stderr,
            )
        raise SystemExit(1) from exc
    except (SingleFileLayoutError, AdjustFactorError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
