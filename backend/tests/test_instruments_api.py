from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from tick.core.config import settings
from tick.main import create_app
from tick.market.instruments_cache import load_instruments_into_memory
from tick.market.schema import INSTRUMENT_COLUMNS


def _seed_instruments(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()
    updated = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
    table = pa.table(
        {
            "symbol": ["000300.SH", "600519.SH", "000001.SZ"],
            "ticker": ["000300", "600519", "000001"],
            "name": ["沪深300", "贵州茅台", "平安银行"],
            "exchange": ["SH", "SH", "SZ"],
            "asset_type": ["a-share-index", "a-share", "a-share"],
            "currency": ["CNY", "CNY", "CNY"],
            "list_date": [date(2005, 4, 8), date(2001, 8, 27), date(1991, 4, 3)],
            "end_date": [None, None, None],
            "last_trade_date": [None, None, None],
            "last_delivery_date": [None, None, None],
            "updated_at": [updated, updated, updated],
        }
    ).select(list(INSTRUMENT_COLUMNS))
    pq.write_table(table, paths.market_instruments)
    load_instruments_into_memory()


def test_list_instruments_default_all(tmp_path, monkeypatch) -> None:
    _seed_instruments(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/instruments")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [item["symbol"] for item in body["items"]] == [
        "000001.SZ",
        "000300.SH",
        "600519.SH",
    ]


def test_list_instruments_filter_and_paginate(tmp_path, monkeypatch) -> None:
    _seed_instruments(tmp_path, monkeypatch)
    client = TestClient(create_app())

    by_type = client.get("/api/v1/instruments", params={"asset_type": "a-share"})
    assert by_type.status_code == 200
    assert by_type.json()["total"] == 2

    by_q = client.get("/api/v1/instruments", params={"q": "茅台"})
    assert by_q.status_code == 200
    assert by_q.json()["total"] == 1
    assert by_q.json()["items"][0]["symbol"] == "600519.SH"

    page = client.get("/api/v1/instruments", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1
    assert page.json()["items"][0]["symbol"] == "000300.SH"


def test_list_instruments_rejects_unknown_asset_type(tmp_path, monkeypatch) -> None:
    _seed_instruments(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/instruments", params={"asset_type": "nope"})
    assert response.status_code == 422
