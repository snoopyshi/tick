"""Fetch the A-share trading calendar via Fuyao and write the canonical table."""

from __future__ import annotations

import argparse
import logging
import tempfile
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.market.fuyao_calendar_adapter import (
    SHANGHAI,
    trading_days_to_canonical,
    trading_days_to_raw,
)
from tick.market.fuyao_client import fetch_trading_day_range
from tick.market.manifest import (
    min_max_date,
    produced_at_now,
    publish_parquet_with_manifest,
)
from tick.market.schema import TRADING_CALENDAR_COLUMNS, VENDOR_THS

logger = logging.getLogger(__name__)

# Local daily bars start on this session. The API allows ten natural years
# per call, so a longer range is requested as several windows.
DEFAULT_START = date(2016, 11, 17)


def ingest_fuyao_calendar(
    *,
    raw_path: Path | None = None,
    output_path: Path | None = None,
    start: date | None = None,
    end: date | None = None,
    fetch: bool = True,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Path:
    """Write the raw snapshot, then the canonical trading-day parquet.

    ``symbols`` in the manifest is 0 because a trading day has no symbol.
    """
    paths = settings.paths
    paths.ensure()
    source = raw_path or paths.raw_ths_calendar
    target = output_path or paths.market_calendar

    if fetch:
        key = (api_key if api_key is not None else settings.fuyao_key).strip()
        if not key:
            raise ValueError(
                "FUYAO_KEY is empty; set it in .env or pass --api-key "
                "(or use --no-fetch with an existing raw parquet)"
            )
        window_start = start or DEFAULT_START
        window_end = end or datetime.now(SHANGHAI).date()
        items, snapshot_ms = fetch_trading_day_range(
            base_url=base_url or settings.fuyao_base_url,
            api_key=key,
            start=window_start,
            end=window_end,
        )
        raw = trading_days_to_raw(items, snapshot_ms=snapshot_ms)
        logger.info("writing Fuyao raw calendar to %s (%s rows)", source, raw.num_rows)
        _atomic_write_parquet(raw, source)
    else:
        if not source.is_file():
            raise FileNotFoundError(f"Fuyao raw calendar parquet not found: {source}")
        logger.info("reading Fuyao raw calendar from %s", source)
        raw = pq.read_table(source)

    canonical = trading_days_to_canonical(raw)
    snapshot_values = {
        value for value in raw["snapshot_ms"].to_pylist() if value is not None
    }
    if len(snapshot_values) == 1:
        snapshot_id = str(next(iter(snapshot_values)))
    else:
        snapshot_id = "trading-days"
    min_date, max_date = min_max_date(canonical, "trade_date")
    manifest: dict[str, object] = {
        "capability_id": "market.trading_calendar",
        "schema_version": 1,
        "columns": list(TRADING_CALENDAR_COLUMNS),
        "rows": canonical.num_rows,
        "symbols": 0,
        "vendor": VENDOR_THS,
        "snapshot_id": snapshot_id,
        "produced_at": produced_at_now(),
    }
    if min_date is not None and max_date is not None:
        manifest["min_date"] = min_date
        manifest["max_date"] = max_date
    publish_parquet_with_manifest(canonical, target, manifest)
    logger.info("ingest done: %s (%s rows)", target, canonical.num_rows)
    return target


def _atomic_write_parquet(table: pa.Table, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        suffix=".parquet.tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        pq.write_table(table, tmp_path, compression="zstd")
        tmp_path.replace(target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _parse_date(value: str) -> date:
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"date must be YYYYMMDD or YYYY-MM-DD, got {value!r}"
        ) from exc


def main() -> None:
    configure_tick_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Fuyao A-share trading days into raw parquet, then write "
            "the canonical calendar under DATA_DIR/market/calendar/."
        ),
    )
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        default=None,
        help=f"Inclusive start, YYYYMMDD (default: {DEFAULT_START.isoformat()}).",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=None,
        help="Inclusive end, YYYYMMDD (default: today in Asia/Shanghai).",
    )
    parser.add_argument("--raw", type=Path, default=None, help="Raw parquet path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Canonical parquet path.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip the API and convert an existing raw parquet.",
    )
    parser.add_argument("--api-key", default=None, help="Override FUYAO_KEY.")
    parser.add_argument("--base-url", default=None, help="Override FUYAO_BASE_URL.")
    args = parser.parse_args()
    ingest_fuyao_calendar(
        raw_path=args.raw,
        output_path=args.output,
        start=args.start_date,
        end=args.end_date,
        fetch=not args.no_fetch,
        api_key=args.api_key,
        base_url=args.base_url,
    )


if __name__ == "__main__":
    main()
