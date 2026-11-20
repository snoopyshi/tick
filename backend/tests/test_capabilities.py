import json
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from tick.core.config import settings
from tick.main import create_app
from tick.market.catalog import get_capability, list_capabilities
from tick.market.manifest import manifest_path_for
from tick.market.schema import OHLCV_1D_COLUMNS


def _ohlcv_table() -> pa.Table:
    return pa.table(
        {
            "symbol": ["000001.SZ"],
            "trade_date": [date(2024, 1, 2)],
            "open": [10.0],
            "high": [10.0],
            "low": [10.0],
            "close": [10.0],
            "volume": [1.0],
            "amount": [10.0],
            "adjust": ["none"],
            "vendor": ["ths"],
            "currency": ["CNY"],
        }
    ).select(list(OHLCV_1D_COLUMNS))


def _manifest_for(table: pa.Table, path, **overrides) -> dict:
    payload = {
        "capability_id": "market.ohlcv.1d",
        "schema_version": 1,
        "columns": list(OHLCV_1D_COLUMNS),
        "rows": table.num_rows,
        "bytes": path.stat().st_size,
        "symbols": 1,
        "vendor": "ths",
        "snapshot_id": "sample",
        "produced_at": "2026-11-19T05:30:00Z",
        "adjust": "none",
        "min_date": "2024-01-02",
        "max_date": "2024-01-02",
    }
    payload.update(overrides)
    return payload


def _write_ready_ohlcv() -> None:
    path = settings.paths.market_ohlcv_1d
    path.parent.mkdir(parents=True, exist_ok=True)
    table = _ohlcv_table()
    pq.write_table(table, path)
    manifest = _manifest_for(table, path)
    manifest_path_for(path).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_missing_parquet_is_missing() -> None:
    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "missing"
    assert view.issues == ("parquet_not_found",)
    assert view.coverage is None


def test_file_without_manifest_is_invalid() -> None:
    path = settings.paths.market_ohlcv_1d
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_ohlcv_table(), path)

    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "invalid"
    assert view.issues == ("manifest_not_found",)
    assert view.coverage is None


def test_corrupt_manifest_does_not_hide_other_capabilities() -> None:
    path = settings.paths.market_ohlcv_1d
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_ohlcv_table(), path)
    manifest_path_for(path).write_text("{", encoding="utf-8")

    views = {item.id: item for item in list_capabilities()}
    assert views["market.ohlcv.1d"].status == "invalid"
    assert views["market.ohlcv.1d"].issues == ("manifest_unreadable",)
    assert views["market.instruments"].status == "missing"
    assert views["market.corp_actions"].status == "missing"
    assert views["market.adjust_factors"].status == "missing"


def test_ready_when_manifest_matches_file() -> None:
    _write_ready_ohlcv()
    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "ready"
    assert view.issues == ()
    assert view.adjust == "none"
    assert view.path == "market/ohlcv/1d/a_share_daily_k_1d.parquet"
    assert view.coverage is not None
    assert view.coverage.rows == 1
    assert view.coverage.symbols == 1
    assert view.coverage.min_date == "2024-01-02"


def test_multiple_mismatches_are_all_reported() -> None:
    path = settings.paths.market_ohlcv_1d
    path.parent.mkdir(parents=True, exist_ok=True)
    table = _ohlcv_table()
    pq.write_table(table, path)
    manifest = _manifest_for(
        table,
        path,
        columns=["close", "symbol"],
        adjust="qfq",
        rows=99,
        bytes=1,
        schema_version=2,
        capability_id="other",
    )
    manifest_path_for(path).write_text(json.dumps(manifest), encoding="utf-8")

    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "invalid"
    assert view.issues == (
        "schema_version_unsupported",
        "capability_id_mismatch",
        "columns_mismatch",
        "adjust_mismatch",
        "rows_mismatch",
        "bytes_mismatch",
    )
    assert view.coverage is not None
    assert view.coverage.rows == 99


def test_unknown_capability_is_none() -> None:
    assert get_capability("missing.capability") is None


def test_list_endpoint_and_unknown_id() -> None:
    _write_ready_ohlcv()
    client = TestClient(create_app())

    listed = client.get("/api/v1/data/capabilities")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 4
    ohlcv = next(item for item in body["items"] if item["id"] == "market.ohlcv.1d")
    assert ohlcv["status"] == "ready"
    assert ohlcv["path"] == "market/ohlcv/1d/a_share_daily_k_1d.parquet"
    missing = next(item for item in body["items"] if item["id"] == "market.instruments")
    assert missing["status"] == "missing"
    assert missing["coverage"] is None

    unknown = client.get("/api/v1/data/capabilities/not-a-capability")
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "unknown capability"


def test_known_missing_capability_returns_200() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/data/capabilities/market.adjust_factors")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing"
    assert body["issues"] == ["parquet_not_found"]
    assert body["depends_on"] == ["market.ohlcv.1d", "market.corp_actions"]


def test_publish_writes_bytes_and_manifest(tmp_path) -> None:
    from tick.market.manifest import publish_parquet_with_manifest

    target = tmp_path / "market" / "ohlcv" / "1d" / "a_share_daily_k_1d.parquet"
    table = _ohlcv_table()
    publish_parquet_with_manifest(
        table,
        target,
        {
            "capability_id": "market.ohlcv.1d",
            "schema_version": 1,
            "columns": list(OHLCV_1D_COLUMNS),
            "rows": table.num_rows,
            "symbols": 1,
            "vendor": "ths",
            "snapshot_id": "sample",
            "produced_at": "2026-11-19T05:30:00Z",
            "adjust": "none",
        },
    )
    assert target.is_file()
    manifest = json.loads(manifest_path_for(target).read_text(encoding="utf-8"))
    assert manifest["bytes"] == target.stat().st_size
    assert manifest["rows"] == 1


def test_publish_removes_parquet_when_manifest_replace_fails(
    tmp_path, monkeypatch
) -> None:
    from pathlib import Path

    from tick.market.manifest import publish_parquet_with_manifest

    target = tmp_path / "bars.parquet"
    target.write_bytes(b"previous")
    real_replace = Path.replace
    calls = {"n": 0}

    def flaky_replace(self: Path, destination: Path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("manifest replace failed")
        return real_replace(self, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    with pytest.raises(OSError, match="manifest replace failed"):
        publish_parquet_with_manifest(
            _ohlcv_table(),
            target,
            {
                "capability_id": "market.ohlcv.1d",
                "schema_version": 1,
                "columns": list(OHLCV_1D_COLUMNS),
                "rows": 1,
                "symbols": 1,
                "vendor": "ths",
                "snapshot_id": "sample",
                "produced_at": "2026-11-19T05:30:00Z",
            },
        )
    assert not target.exists()
    assert list(tmp_path.glob("*.tmp")) == []
