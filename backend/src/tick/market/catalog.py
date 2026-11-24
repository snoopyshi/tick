"""Declared data capabilities joined with on-disk coverage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from tick.core.config import settings
from tick.market.manifest import load_manifest
from tick.market.partitions import load_dataset_manifest, trade_date_partition
from tick.market.schema import (
    ADJUST_FACTOR_COLUMNS,
    CORP_ACTION_COLUMNS,
    INSTRUMENT_COLUMNS,
    OHLCV_1D_COLUMNS,
    TRADING_CALENDAR_COLUMNS,
)

_ISSUE_ORDER = (
    "schema_version_unsupported",
    "capability_id_mismatch",
    "columns_mismatch",
    "adjust_mismatch",
    "rows_mismatch",
    "bytes_mismatch",
)


@dataclass(frozen=True, slots=True)
class CapabilityDecl:
    id: str
    title: str
    grain: tuple[str, ...]
    columns: tuple[str, ...]
    adjust: str | None
    depends_on: tuple[str, ...]
    relative_path: str
    producer: str


@dataclass(frozen=True, slots=True)
class Coverage:
    rows: int
    bytes: int
    symbols: int
    vendor: str
    snapshot_id: str
    produced_at: str
    min_date: str | None = None
    max_date: str | None = None
    asset_types: dict[str, int] | None = None
    events_applied: int | None = None
    events_before_window: int | None = None
    events_after_window: int | None = None
    events_zero: int | None = None
    events_no_bars: int | None = None


@dataclass(frozen=True, slots=True)
class CapabilityView:
    id: str
    title: str
    status: str
    grain: tuple[str, ...]
    columns: tuple[str, ...]
    adjust: str | None
    depends_on: tuple[str, ...]
    producer: str
    path: str
    coverage: Coverage | None
    issues: tuple[str, ...]


CAPABILITIES: tuple[CapabilityDecl, ...] = (
    CapabilityDecl(
        id="market.instruments",
        title="标的",
        grain=("symbol",),
        columns=INSTRUMENT_COLUMNS,
        adjust=None,
        depends_on=(),
        relative_path="market/instruments/instruments.parquet",
        producer="tick-ingest-fuyao-tickers",
    ),
    CapabilityDecl(
        id="market.ohlcv.1d",
        title="不复权日K",
        grain=("symbol", "trade_date"),
        columns=OHLCV_1D_COLUMNS,
        adjust="none",
        depends_on=(),
        relative_path="market/ohlcv/1d/a_share_daily_k_1d.parquet",
        producer="tick-ingest-ths-daily",
    ),
    CapabilityDecl(
        id="market.corp_actions",
        title="除权事件",
        grain=("symbol", "ex_date"),
        columns=CORP_ACTION_COLUMNS,
        adjust=None,
        depends_on=(),
        relative_path="market/corp_actions/a_share_corp_actions.parquet",
        producer="tick-ingest-ths-corp-actions",
    ),
    CapabilityDecl(
        id="market.adjust_factors",
        title="复权因子",
        grain=("symbol", "trade_date"),
        columns=ADJUST_FACTOR_COLUMNS,
        adjust=None,
        depends_on=("market.ohlcv.1d", "market.corp_actions"),
        relative_path="market/adjust_factors/a_share_adjust_factors.parquet",
        producer="tick-ingest-adjust-factors",
    ),
    CapabilityDecl(
        id="market.trading_calendar",
        title="交易日历",
        grain=("trade_date",),
        columns=TRADING_CALENDAR_COLUMNS,
        adjust=None,
        depends_on=(),
        relative_path="market/calendar/a_share_trading_days.parquet",
        producer="tick-ingest-fuyao-calendar",
    ),
)

_BY_ID = {item.id: item for item in CAPABILITIES}


def list_capabilities() -> list[CapabilityView]:
    root = settings.paths.root
    return [evaluate_capability(item, root) for item in CAPABILITIES]


def get_capability(capability_id: str) -> CapabilityView | None:
    declaration = _BY_ID.get(capability_id)
    if declaration is None:
        return None
    return evaluate_capability(declaration, settings.paths.root)


def evaluate_capability(declaration: CapabilityDecl, root: Path) -> CapabilityView:
    dataset = _evaluate_dataset_if_present(declaration, root)
    if dataset is not None:
        return dataset
    parquet_path = root / declaration.relative_path
    if not parquet_path.is_file():
        return _view(
            declaration,
            coverage=None,
            issues=("parquet_not_found",),
            status="missing",
        )

    loaded = load_manifest(parquet_path)
    if loaded.kind == "not_found":
        return _view(declaration, coverage=None, issues=("manifest_not_found",))
    if loaded.kind == "unreadable" or loaded.data is None:
        return _view(declaration, coverage=None, issues=("manifest_unreadable",))

    data = loaded.data
    issues: list[str] = []
    if data["schema_version"] != 1:
        issues.append("schema_version_unsupported")
    if data["capability_id"] != declaration.id:
        issues.append("capability_id_mismatch")

    parquet = pq.ParquetFile(parquet_path)
    file_columns = list(parquet.schema_arrow.names)
    file_rows = parquet.metadata.num_rows
    if data["columns"] != list(declaration.columns) or file_columns != list(
        declaration.columns
    ):
        issues.append("columns_mismatch")
    if declaration.adjust is not None and data.get("adjust") != declaration.adjust:
        issues.append("adjust_mismatch")
    if data["rows"] != file_rows:
        issues.append("rows_mismatch")
    if data["bytes"] != parquet_path.stat().st_size:
        issues.append("bytes_mismatch")

    ordered = tuple(code for code in _ISSUE_ORDER if code in issues)
    status = "ready" if not ordered else "invalid"
    return _view(declaration, coverage=_coverage(data), issues=ordered, status=status)


def _evaluate_dataset_if_present(
    declaration: CapabilityDecl,
    root: Path,
) -> CapabilityView | None:
    """Use the trade-date catalog when it exists. Otherwise keep the single file."""
    if declaration.id == "market.ohlcv.1d":
        manifest_path = root / "market" / "ohlcv" / "1d" / "manifest.json"
        dataset_dir = root / "market" / "ohlcv" / "1d"
    elif declaration.id == "market.adjust_factors":
        manifest_path = root / "market" / "adjust_factors" / "manifest.json"
        dataset_dir = root / "market" / "adjust_factors"
    else:
        return None
    has_parts = any(dataset_dir.glob("trade_date=*/part.parquet"))
    if not manifest_path.is_file() and not has_parts:
        return None
    if not manifest_path.is_file():
        return _view(declaration, coverage=None, issues=("manifest_not_found",))

    loaded = load_dataset_manifest(manifest_path)
    if loaded.kind == "unreadable" or loaded.data is None:
        return _view(declaration, coverage=None, issues=("manifest_unreadable",))
    data = loaded.data
    if not data["partitions"]:
        return _view(declaration, coverage=None, issues=("manifest_unreadable",))
    issues: list[str] = []
    if data["schema_version"] != 2:
        issues.append("schema_version_unsupported")
    if data["capability_id"] != declaration.id:
        issues.append("capability_id_mismatch")
    if data["columns"] != list(declaration.columns):
        issues.append("columns_mismatch")
    if declaration.adjust is not None and data.get("adjust") != declaration.adjust:
        issues.append("adjust_mismatch")
    recorded = sum(item["rows"] for item in data["partitions"])
    if data["rows"] != recorded:
        issues.append("rows_mismatch")
    watermark = data["watermark"]
    part_rows = next(
        item["rows"]
        for item in data["partitions"]
        if item["trade_date"] == watermark
    )
    watermark_file = trade_date_partition(dataset_dir, watermark)
    if not watermark_file.is_file():
        issues.append("rows_mismatch")
    else:
        parquet = pq.ParquetFile(watermark_file)
        if list(parquet.schema_arrow.names) != list(declaration.columns):
            issues.append("columns_mismatch")
        if parquet.metadata.num_rows != part_rows:
            issues.append("rows_mismatch")
    ordered = tuple(code for code in _ISSUE_ORDER if code in issues)
    status = "ready" if not ordered else "invalid"
    view = _view(declaration, coverage=_coverage(data), issues=ordered, status=status)
    return CapabilityView(
        id=view.id,
        title=view.title,
        status=view.status,
        grain=view.grain,
        columns=view.columns,
        adjust=view.adjust,
        depends_on=view.depends_on,
        producer=view.producer,
        path=dataset_dir.relative_to(root).as_posix(),
        coverage=view.coverage,
        issues=view.issues,
    )


def _view(
    declaration: CapabilityDecl,
    *,
    coverage: Coverage | None,
    issues: tuple[str, ...],
    status: str = "invalid",
) -> CapabilityView:
    return CapabilityView(
        id=declaration.id,
        title=declaration.title,
        status=status,
        grain=declaration.grain,
        columns=declaration.columns,
        adjust=declaration.adjust,
        depends_on=declaration.depends_on,
        producer=declaration.producer,
        path=declaration.relative_path,
        coverage=coverage,
        issues=issues,
    )


def _coverage(data: dict) -> Coverage:
    return Coverage(
        rows=data["rows"],
        bytes=data["bytes"],
        symbols=data["symbols"],
        vendor=data["vendor"],
        snapshot_id=data["snapshot_id"],
        produced_at=data["produced_at"],
        min_date=_optional_str(data, "min_date"),
        max_date=_optional_str(data, "max_date"),
        asset_types=_optional_asset_types(data),
        events_applied=_optional_int(data, "events_applied"),
        events_before_window=_optional_int(data, "events_before_window"),
        events_after_window=_optional_int(data, "events_after_window"),
        events_zero=_optional_int(data, "events_zero"),
        events_no_bars=_optional_int(data, "events_no_bars"),
    )


def _optional_str(data: dict, key: str) -> str | None:
    value = data.get(key)
    if isinstance(value, str):
        return value
    return None


def _optional_int(data: dict, key: str) -> int | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_asset_types(data: dict) -> dict[str, int] | None:
    value = data.get("asset_types")
    if not isinstance(value, dict):
        return None
    parsed: dict[str, int] = {}
    for key, count in value.items():
        if (
            not isinstance(key, str)
            or isinstance(count, bool)
            or not isinstance(count, int)
        ):
            return None
        parsed[key] = count
    return parsed
