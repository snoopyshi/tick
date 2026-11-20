"""Build the canonical adjust-factor table from ready daily bars and events."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pyarrow.parquet as pq

from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.market.adjust_factors import compute_adjust_factors
from tick.market.catalog import CapabilityView, get_capability
from tick.market.manifest import (
    count_symbols,
    min_max_date,
    produced_at_now,
    publish_parquet_with_manifest,
)
from tick.market.schema import ADJUST_FACTOR_COLUMNS, VENDOR_THS

logger = logging.getLogger(__name__)


class DependencyNotReadyError(RuntimeError):
    def __init__(self, views: list[CapabilityView]) -> None:
        self.views = views
        names = ", ".join(view.id for view in views)
        super().__init__(f"dependencies are not ready: {names}")


def ingest_adjust_factors(*, output_path: Path | None = None) -> Path:
    paths = settings.paths
    paths.ensure()
    target = output_path or paths.market_adjust_factors

    ohlcv = get_capability("market.ohlcv.1d")
    events_view = get_capability("market.corp_actions")
    if ohlcv is None or events_view is None:
        raise RuntimeError("adjust-factor dependencies are not declared")
    blocked = [view for view in (ohlcv, events_view) if view.status != "ready"]
    if blocked:
        raise DependencyNotReadyError(blocked)
    if ohlcv.coverage is None or events_view.coverage is None:
        raise DependencyNotReadyError([ohlcv, events_view])

    bars = pq.read_table(
        paths.market_ohlcv_1d,
        columns=["symbol", "trade_date", "close"],
    )
    events = pq.read_table(paths.market_corp_actions)
    result = compute_adjust_factors(bars, events)

    low, high = min_max_date(result.table, "trade_date")
    manifest: dict = {
        "capability_id": "market.adjust_factors",
        "schema_version": 1,
        "columns": list(ADJUST_FACTOR_COLUMNS),
        "rows": result.table.num_rows,
        "symbols": count_symbols(result.table),
        "vendor": VENDOR_THS,
        "snapshot_id": (
            f"derived:{ohlcv.coverage.snapshot_id}+{events_view.coverage.snapshot_id}"
        ),
        "produced_at": produced_at_now(),
        "events_applied": result.events_applied,
        "events_before_window": result.events_before_window,
        "events_after_window": result.events_after_window,
        "events_zero": result.events_zero,
        "events_no_bars": result.events_no_bars,
    }
    if low is not None and high is not None:
        manifest["min_date"] = low
        manifest["max_date"] = high
    publish_parquet_with_manifest(result.table, target, manifest)
    logger.info("adjust factors written: %s rows=%s", target, result.table.num_rows)
    return target


def main() -> None:
    configure_tick_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Derive canonical adjust factors from ready OHLCV and corp actions."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Canonical output path (default: DATA_DIR/market/adjust_factors/...)",
    )
    args = parser.parse_args()
    try:
        ingest_adjust_factors(output_path=args.output)
    except DependencyNotReadyError as exc:
        for view in exc.views:
            print(
                f"{view.id} status={view.status} issues={list(view.issues)}",
                file=sys.stderr,
            )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
