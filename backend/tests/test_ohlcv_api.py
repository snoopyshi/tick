from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from tick.core.config import settings
from tick.main import create_app
from tick.market.ohlcv_cache import load_ohlcv_1d_into_memory
from tick.market.schema import OHLCV_1D_COLUMNS, VENDOR_THS


def _seed_ohlcv(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()
    table = pa.table(
        {
            "symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "trade_date": [
                date(2016, 11, 17),
                date(2016, 11, 18),
                date(2016, 11, 21),
            ],
            "open": [9.22, 9.21, 9.20],
            "high": [9.22, 9.21, 9.25],
            "low": [9.18, 9.16, 9.15],
            "close": [9.21, 9.18, 9.19],
            "volume": [1.0, 2.0, 3.0],
            "amount": [10.0, 20.0, 30.0],
            "adjust": ["none", "none", "none"],
            "vendor": [VENDOR_THS, VENDOR_THS, VENDOR_THS],
            "currency": ["CNY", "CNY", "CNY"],
        }
    ).select(list(OHLCV_1D_COLUMNS))
    pq.write_table(table, paths.market_ohlcv_1d)
    load_ohlcv_1d_into_memory()


def test_get_ohlcv_1d_returns_full_series_by_default(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "000001.SZ"
    assert len(body["bars"]) == 3
    assert body["bars"][0]["time"] == "2016-11-17"
    assert body["bars"][-1]["time"] == "2016-11-21"


def test_get_ohlcv_1d_returns_recent_bars_with_limit(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "000001.SZ"
    assert len(body["bars"]) == 2
    assert body["bars"][0]["time"] == "2016-11-18"
    assert body["bars"][1]["time"] == "2016-11-21"
    assert body["bars"][1]["close"] == 9.19


def test_get_ohlcv_1d_unknown_symbol_empty(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/999999.SH")
    assert response.status_code == 200
    assert response.json() == {"symbol": "999999.SH", "bars": []}
