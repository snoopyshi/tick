"""Trade-date partitions and their dataset manifest."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from tick.market.manifest import ManifestLoad, load_manifest_file, produced_at_now

PARTITION_NAME = "part.parquet"


def trade_date_partition(dataset_dir: Path, trade_date: str) -> Path:
    """``dataset/trade_date=YYYY-MM-DD/part.parquet``."""
    return dataset_dir / f"trade_date={trade_date}" / PARTITION_NAME


def load_dataset_manifest(path: Path) -> ManifestLoad:
    """Read a schema-version-2 dataset manifest.

    Structural problems (layout, partition list, watermark) are ``unreadable``
    so one bad catalog does not raise into the other capabilities.
    """
    loaded = load_manifest_file(path)
    if loaded.kind != "ok" or loaded.data is None:
        return loaded
    data = loaded.data
    partitions = data.get("partitions")
    watermark = data.get("watermark")
    if data.get("layout") != "trade_date" or not isinstance(partitions, list):
        return ManifestLoad("unreadable")
    if not isinstance(watermark, str) or not isinstance(data.get("batch_dates"), list):
        return ManifestLoad("unreadable")
    dates: list[str] = []
    for item in partitions:
        if not isinstance(item, dict):
            return ManifestLoad("unreadable")
        trade_date = item.get("trade_date")
        rows = item.get("rows")
        size = item.get("bytes")
        if not isinstance(trade_date, str):
            return ManifestLoad("unreadable")
        if isinstance(rows, bool) or not isinstance(rows, int):
            return ManifestLoad("unreadable")
        if isinstance(size, bool) or not isinstance(size, int):
            return ManifestLoad("unreadable")
        dates.append(trade_date)
    if dates and (watermark != max(dates) or data.get("min_date") != min(dates)):
        return ManifestLoad("unreadable")
    if data.get("max_date") not in (None, watermark):
        return ManifestLoad("unreadable")
    return loaded


def dataset_snapshot_id(dates: list[str]) -> str:
    """Stable id for the batch that was just written."""
    ordered = sorted(dates)
    if not ordered:
        return "batch:empty"
    if len(ordered) == 1:
        return f"batch:{ordered[0]}"
    return f"batch:{ordered[0]}..{ordered[-1]}"


def merge_partitions(
    existing: list[dict[str, Any]],
    updates: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """Replace only the dates in ``updates``. Other dates keep their entries."""
    merged = {
        item["trade_date"]: {
            "trade_date": item["trade_date"],
            "rows": item["rows"],
            "bytes": item["bytes"],
        }
        for item in existing
    }
    for trade_date, values in updates.items():
        merged[trade_date] = {
            "trade_date": trade_date,
            "rows": values["rows"],
            "bytes": values["bytes"],
        }
    return [merged[key] for key in sorted(merged)]


def publish_tables(
    files: list[tuple[Path, pa.Table]],
    manifests: Callable[[dict[Path, int]], list[tuple[Path, dict[str, Any]]]],
) -> None:
    """Write every table, then the manifests. Failure restores previous files.

    Temps are written before any official partition is replaced. If a later
    step fails, backups are moved back and temps are removed.
    """
    temps: list[Path] = []
    backups: list[tuple[Path, Path]] = []
    manifest_backups: list[tuple[Path, Path]] = []
    try:
        for final, table in files:
            final.parent.mkdir(parents=True, exist_ok=True)
            tmp = final.with_name(final.name + ".tmp")
            pq.write_table(table, tmp, compression="zstd")
            temps.append(tmp)
        for (final, _), tmp in zip(files, temps, strict=True):
            if final.exists():
                backup = final.with_name(final.name + ".bak")
                final.replace(backup)
                backups.append((backup, final))
            tmp.replace(final)
        temps = []
        sizes = {final: final.stat().st_size for final, _ in files}
        for path, payload in manifests(sizes):
            if path.exists():
                backup = path.with_name(path.name + ".bak")
                path.replace(backup)
                manifest_backups.append((backup, path))
            _write_json(path, payload)
        for backup, _final in backups:
            backup.unlink(missing_ok=True)
        for backup, _path in manifest_backups:
            backup.unlink(missing_ok=True)
    except Exception:
        for backup, final in reversed(backups):
            if backup.exists():
                if final.exists():
                    final.unlink()
                backup.replace(final)
        for backup, path in reversed(manifest_backups):
            if backup.exists():
                if path.exists():
                    path.unlink()
                backup.replace(path)
        for tmp in temps:
            tmp.unlink(missing_ok=True)
        raise


def build_dataset_manifest(
    *,
    capability_id: str,
    columns: tuple[str, ...],
    partitions: list[dict[str, Any]],
    symbols: int,
    snapshot_id: str,
    batch_dates: list[str],
    adjust: str | None = None,
) -> dict[str, Any]:
    """Dataset catalog. ``rows`` and ``bytes`` are sums of the partition index."""
    ordered = sorted(partitions, key=lambda item: item["trade_date"])
    payload: dict[str, Any] = {
        "capability_id": capability_id,
        "schema_version": 2,
        "columns": list(columns),
        "rows": sum(item["rows"] for item in ordered),
        "bytes": sum(item["bytes"] for item in ordered),
        "symbols": symbols,
        "vendor": "ths",
        "snapshot_id": snapshot_id,
        "produced_at": produced_at_now(),
        "layout": "trade_date",
        "watermark": ordered[-1]["trade_date"] if ordered else None,
        "partitions": ordered,
        "batch_dates": sorted(batch_dates),
    }
    if ordered:
        payload["min_date"] = ordered[0]["trade_date"]
        payload["max_date"] = ordered[-1]["trade_date"]
    if adjust is not None:
        payload["adjust"] = adjust
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        suffix=".json.tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
