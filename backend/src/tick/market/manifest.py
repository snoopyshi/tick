"""标准 Parquet 的原子写入，以及旁边的覆盖清单。"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

PUBLIC_MANIFEST_FIELDS: tuple[str, ...] = (
    "capability_id",
    "schema_version",
    "columns",
    "rows",
    "bytes",
    "symbols",
    "vendor",
    "snapshot_id",
    "produced_at",
)


def manifest_path_for(parquet_path: Path) -> Path:
    """由 Parquet 路径得到清单路径，例如 ``bars.parquet`` → ``bars.manifest.json``。

    清单不单独配置路径，注册中心只凭标准文件就能找到它。
    """
    return parquet_path.with_suffix(".manifest.json")


@dataclass(frozen=True, slots=True)
class ManifestLoad:
    """一份清单的读取结果。

    读取失败不抛异常。某一份清单损坏时，注册中心只把这一项标为
    ``invalid``，其他能力仍可返回。

    ``kind`` 为 ``ok`` 时 ``data`` 可用；``not_found`` 表示清单文件不在；
    ``unreadable`` 表示 JSON 损坏，或公共字段缺失、类型不对。
    """

    kind: Literal["ok", "not_found", "unreadable"]
    data: dict[str, Any] | None = None


def load_manifest(parquet_path: Path) -> ManifestLoad:
    """读取 Parquet 旁边的清单，返回 :class:`ManifestLoad`。"""
    return load_manifest_file(manifest_path_for(parquet_path))


def load_manifest_file(path: Path) -> ManifestLoad:
    """读取指定路径上的清单 JSON。文件不在或内容不合法时不抛异常。"""
    if not path.is_file():
        return ManifestLoad("not_found")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ManifestLoad("unreadable")
    if not isinstance(parsed, dict):
        return ManifestLoad("unreadable")
    if not _public_fields_ok(parsed):
        return ManifestLoad("unreadable")
    return ManifestLoad("ok", parsed)


def publish_parquet_with_manifest(
    table: pa.Table,
    parquet_path: Path,
    manifest: dict[str, Any],
) -> None:
    """先写 Parquet，再写清单。清单写失败时删掉刚替换上的 Parquet。

    ``manifest`` 要带齐公共字段，但不要带最终的 ``bytes``：字节数在正式文件
    替换完成后才填入。替换已经成功又写清单失败时，上一版文件也已经不在，
    这里会把新文件一起删掉，让该能力变成 ``missing``，而不是一份对不上的
    ``invalid``。调用方应在此之前完成口径和主键检查。
    """
    payload = dict(manifest)
    payload.pop("bytes", None)
    if not _public_fields_ok({**payload, "bytes": 0}):
        raise ValueError("manifest is missing public fields")

    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_parquet: Path | None = None
    tmp_manifest: Path | None = None
    replaced = False
    try:
        with tempfile.NamedTemporaryFile(
            dir=parquet_path.parent,
            suffix=".parquet.tmp",
            delete=False,
        ) as tmp:
            tmp_parquet = Path(tmp.name)
        pq.write_table(table, tmp_parquet, compression="zstd")
        tmp_parquet.replace(parquet_path)
        replaced = True
        tmp_parquet.unlink(missing_ok=True)
        tmp_parquet = None

        payload["bytes"] = parquet_path.stat().st_size
        manifest_path = manifest_path_for(parquet_path)
        with tempfile.NamedTemporaryFile(
            dir=manifest_path.parent,
            suffix=".manifest.json.tmp",
            delete=False,
        ) as tmp:
            tmp_manifest = Path(tmp.name)
        tmp_manifest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_manifest.replace(manifest_path)
        tmp_manifest = None
    except Exception:
        if tmp_parquet is not None:
            tmp_parquet.unlink(missing_ok=True)
        if tmp_manifest is not None:
            tmp_manifest.unlink(missing_ok=True)
        if replaced:
            parquet_path.unlink(missing_ok=True)
        raise


def produced_at_now() -> str:
    """当前 UTC 时间，秒精度，形如 ``2026-11-19T05:30:00Z``。

    只写入清单。写进 Parquet 会让同一份输入每次入库的文件字节数变化。
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_symbols(table: pa.Table) -> int:
    """清单字段 ``symbols``：``symbol`` 列的去重个数。空表返回 0。"""
    if table.num_rows == 0:
        return 0
    return int(pc.count_distinct(table["symbol"]).as_py())


def min_max_date(table: pa.Table, column: str) -> tuple[str | None, str | None]:
    """日期列的最小值和最大值，格式 ``YYYY-MM-DD``。

    空表或该列全空时返回 ``(None, None)``，调用方就不把日期写入清单。
    """
    if table.num_rows == 0:
        return None, None
    low = pc.min(table[column]).as_py()
    high = pc.max(table[column]).as_py()
    if low is None or high is None:
        return None, None
    return low.isoformat(), high.isoformat()


def asset_type_counts(table: pa.Table) -> dict[str, int]:
    """标的清单的 ``asset_types``：每个 ``asset_type`` 有多少行。"""
    if table.num_rows == 0:
        return {}
    counted = pc.value_counts(table["asset_type"]).to_pylist()
    return {item["values"]: int(item["counts"]) for item in counted}


def require_unique_keys(table: pa.Table, columns: tuple[str, ...]) -> None:
    """主键有重复时抛出 ``ValueError``。

    必须在 :func:`publish_parquet_with_manifest` 之前调用。检查失败时正式文件
    还没被替换。
    """
    if table.num_rows == 0:
        return
    if len(columns) == 1:
        distinct = pc.count_distinct(table[columns[0]]).as_py()
    else:
        key = pc.binary_join_element_wise(
            pc.cast(table[columns[0]], pa.string()),
            pc.cast(table[columns[1]], pa.string()),
            "|",
        )
        distinct = pc.count_distinct(key).as_py()
    if distinct != table.num_rows:
        raise ValueError(f"duplicate {', '.join(columns)}")


def require_adjust_none(table: pa.Table) -> None:
    """日 K 的 ``adjust`` 必须全部是 ``none``，否则抛出 ``ValueError``。

    标准价格只存不复权行情。空值或其他口径都拒绝写入，避免和复权因子表混用。
    """
    if table.num_rows == 0:
        return
    adjust = table["adjust"]
    if pc.any(pc.is_null(adjust)).as_py():
        raise ValueError("adjust contains null")
    mismatched = pc.not_equal(adjust, "none")
    if pc.any(pc.fill_null(mismatched, True)).as_py():
        raise ValueError("adjust must be none")


def _public_fields_ok(data: dict[str, Any]) -> bool:
    """公共字段齐全且类型正确时返回 True。

    ``schema_version``、``rows``、``bytes``、``symbols`` 不接受 ``bool``。
    ``bool`` 是 ``int`` 的子类，直接用 ``isinstance(..., int)`` 会把 ``True`` 当成 1。
    """
    for field in PUBLIC_MANIFEST_FIELDS:
        if field not in data:
            return False
    if (
        not isinstance(data["capability_id"], str)
        or not isinstance(data["vendor"], str)
        or not isinstance(data["snapshot_id"], str)
        or not isinstance(data["produced_at"], str)
    ):
        return False
    if isinstance(data["schema_version"], bool) or not isinstance(
        data["schema_version"], int
    ):
        return False
    for field in ("rows", "bytes", "symbols"):
        if isinstance(data[field], bool) or not isinstance(data[field], int):
            return False
    columns = data["columns"]
    if not isinstance(columns, list) or any(
        not isinstance(item, str) for item in columns
    ):
        return False
    return True
