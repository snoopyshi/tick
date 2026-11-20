"""Fetch THS ticker list via Fuyao gateway and write canonical instruments."""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.market.fuyao_client import fetch_all_tickers
from tick.market.fuyao_tickers_adapter import (
    fuyao_items_to_raw_table,
    fuyao_tickers_to_canonical,
)
from tick.market.manifest import (
    asset_type_counts,
    count_symbols,
    produced_at_now,
    publish_parquet_with_manifest,
    require_unique_keys,
)
from tick.market.schema import (
    ASSET_TYPES,
    DEFAULT_TICKER_ASSET_TYPES,
    INSTRUMENT_COLUMNS,
    VENDOR_THS,
)

logger = logging.getLogger(__name__)


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


def _snapshot_id(raw: pa.Table) -> str:
    if "snapshot_ms" not in raw.column_names:
        return "tickers"
    values = {value for value in raw["snapshot_ms"].to_pylist() if value is not None}
    if len(values) == 1:
        return str(next(iter(values)))
    return "tickers"


def _parse_asset_types(value: str | None) -> list[str] | None:
    if value is None or not value.strip() or value.strip() == "*":
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    unknown = sorted({part for part in parts if part not in ASSET_TYPES})
    if unknown:
        raise ValueError(
            f"unknown asset_type(s): {unknown}; allowed={sorted(ASSET_TYPES)}"
        )
    return parts


def ingest_fuyao_tickers(
    *,
    raw_path: Path | None = None,
    instruments_path: Path | None = None,
    vendor_map_path: Path | None = None,
    asset_types: list[str] | None = None,
    fetch: bool = True,
    api_key: str | None = None,
    base_url: str | None = None,
    limit: int = 1000,
) -> tuple[Path, Path]:
    """Write raw snapshot (optional fetch) then canonical instruments + map.

    Returns ``(instruments_path, vendor_symbol_map_path)``.
    """
    paths = settings.paths
    paths.ensure()

    source = raw_path or paths.raw_ths_tickers
    instruments_target = instruments_path or paths.market_instruments
    vendor_map_target = vendor_map_path or paths.market_vendor_symbol_map

    if fetch:
        key = (api_key if api_key is not None else settings.fuyao_key).strip()
        if not key:
            raise ValueError(
                "FUYAO_KEY is empty; set it in .env or pass --api-key "
                "(or use --no-fetch with an existing raw parquet)"
            )
        items, snapshot_ms = fetch_all_tickers(
            base_url=base_url or settings.fuyao_base_url,
            api_key=key,
            asset_types=asset_types,
            limit=limit,
        )
        raw = fuyao_items_to_raw_table(items, snapshot_ms=snapshot_ms)
        logger.info("writing Fuyao raw tickers to %s (%s rows)", source, raw.num_rows)
        _atomic_write_parquet(raw, source)
    else:
        if not source.is_file():
            raise FileNotFoundError(f"Fuyao raw tickers parquet not found: {source}")
        logger.info("reading Fuyao raw tickers from %s", source)
        raw = pq.read_table(source)

    instruments, vendor_map = fuyao_tickers_to_canonical(raw)
    require_unique_keys(instruments, ("symbol",))
    logger.info(
        "canonical instruments=%s vendor_map=%s",
        instruments.num_rows,
        vendor_map.num_rows,
    )
    manifest = {
        "capability_id": "market.instruments",
        "schema_version": 1,
        "columns": list(INSTRUMENT_COLUMNS),
        "rows": instruments.num_rows,
        "symbols": count_symbols(instruments),
        "vendor": VENDOR_THS,
        "snapshot_id": _snapshot_id(raw),
        "produced_at": produced_at_now(),
        "asset_types": asset_type_counts(instruments),
    }
    publish_parquet_with_manifest(instruments, instruments_target, manifest)
    _atomic_write_parquet(vendor_map, vendor_map_target)
    logger.info(
        "ingest done: %s (%s rows), %s (%s rows)",
        instruments_target,
        instruments.num_rows,
        vendor_map_target,
        vendor_map.num_rows,
    )
    return instruments_target, vendor_map_target


def main() -> None:
    configure_tick_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Fuyao ticker list into raw parquet, then write canonical "
            "instruments + vendor_symbol_map under DATA_DIR/market/instruments/."
        ),
    )
    ## 默认拉取股票和指数
    parser.add_argument(
        "--asset-type",
        default=",".join(DEFAULT_TICKER_ASSET_TYPES),
        help=(
            "Comma-separated asset types "
            f"(default: {','.join(DEFAULT_TICKER_ASSET_TYPES)}). "
            "Use * for all types returned by Fuyao."
        ),
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=None,
        help="Raw THS tickers parquet path (default: DATA_DIR/raw/ths/tickers/...)",
    )
    parser.add_argument(
        "--instruments-output",
        type=Path,
        default=None,
        help="Canonical instruments parquet path",
    )
    parser.add_argument(
        "--vendor-map-output",
        type=Path,
        default=None,
        help="Canonical vendor_symbol_map parquet path",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip API fetch; convert an existing raw parquet only",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override FUYAO_KEY from settings",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override FUYAO_BASE_URL from settings",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Page size for Fuyao list API (max 10000)",
    )
    args = parser.parse_args()
    asset_types = _parse_asset_types(args.asset_type)
    ingest_fuyao_tickers(
        raw_path=args.raw,
        instruments_path=args.instruments_output,
        vendor_map_path=args.vendor_map_output,
        asset_types=asset_types,
        fetch=not args.no_fetch,
        api_key=args.api_key,
        base_url=args.base_url,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
