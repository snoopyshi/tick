import math
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from tick.core.config import settings
from tick.main import create_app
from tick.market.factor_cache import load_adjust_factors_into_memory
from tick.market.ohlcv_cache import (
    clear_ohlcv_1d_cache,
    load_ohlcv_1d_into_memory,
)
from tick.market.schema import ADJUST_FACTOR_COLUMNS, OHLCV_1D_COLUMNS, VENDOR_THS


def _write_bars(rows: list[tuple[date, float, float]]) -> None:
    table = pa.table(
        {
            "symbol": ["000001.SZ"] * len(rows),
            "trade_date": [row[0] for row in rows],
            "open": [row[1] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[1] for row in rows],
            "close": [row[2] for row in rows],
            "volume": [float(index + 1) for index in range(len(rows))],
            "amount": [row[2] for row in rows],
            "adjust": ["none"] * len(rows),
            "vendor": [VENDOR_THS] * len(rows),
            "currency": ["CNY"] * len(rows),
        }
    ).select(list(OHLCV_1D_COLUMNS))
    pq.write_table(table, settings.paths.market_ohlcv_1d)


def _write_factors(rows: list[tuple[date, float]]) -> None:
    table = pa.table(
        {
            "symbol": ["000001.SZ"] * len(rows),
            "trade_date": [row[0] for row in rows],
            "factor": [row[1] for row in rows],
            "vendor": [VENDOR_THS] * len(rows),
        }
    ).select(list(ADJUST_FACTOR_COLUMNS))
    pq.write_table(table, settings.paths.market_adjust_factors)


def _use_data_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()


def _seed_ohlcv(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    rows = [
        (date(2016, 11, 17), 9.22, 9.21),
        (date(2016, 11, 18), 9.21, 9.18),
        (date(2016, 11, 21), 9.20, 9.19),
    ]
    _write_bars(rows)
    _write_factors([(row[0], 1.0) for row in rows])
    _load_caches()


def _load_caches() -> None:
    load_ohlcv_1d_into_memory()
    load_adjust_factors_into_memory()


def test_get_ohlcv_1d_returns_full_series_by_default(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "000001.SZ"
    assert body["adjust"] == "qfq"
    assert len(body["bars"]) == 3
    assert body["bars"][0]["time"] == "2016-11-17"
    assert body["bars"][0]["close"] == 9.21
    assert body["bars"][0]["volume"] == 1.0
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
    assert body["bars"][0]["close"] == 9.18
    assert body["bars"][1]["close"] == 9.19


def test_get_ohlcv_1d_unknown_symbol_empty(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/999999.SH")
    assert response.status_code == 200
    assert response.json() == {"symbol": "999999.SH", "adjust": "qfq", "bars": []}


def test_forward_adjust_uses_the_full_series_anchor(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    _write_bars([(day1, 10.0, 10.0), (day2, 9.0, 9.0)])
    _write_factors([(day1, 1.0), (day2, 1 / 0.9)])
    _load_caches()
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ")
    assert response.status_code == 200
    body = response.json()
    assert math.isclose(body["bars"][0]["close"], 9.0)
    assert math.isclose(body["bars"][1]["close"], 9.0)
    assert body["bars"][0]["volume"] == 1.0
    assert body["bars"][1]["volume"] == 2.0

    limited = client.get("/api/v1/ohlcv/1d/000001.SZ", params={"limit": 2})
    assert limited.status_code == 200
    window = limited.json()["bars"]
    assert math.isclose(window[0]["close"], 9.0)
    assert math.isclose(window[1]["close"], 9.0)

    latest = client.get("/api/v1/ohlcv/1d/000001.SZ", params={"limit": 1})
    assert latest.status_code == 200
    assert math.isclose(latest.json()["bars"][0]["close"], 9.0)


def test_adjust_none_returns_raw_prices(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    _write_bars([(day1, 10.0, 10.0), (day2, 9.0, 9.0)])
    _write_factors([(day1, 1.0), (day2, 1 / 0.9)])
    _load_caches()
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ", params={"adjust": "none"})
    assert response.status_code == 200
    body = response.json()
    assert body["adjust"] == "none"
    assert body["bars"][0]["close"] == 10.0
    assert body["bars"][1]["close"] == 9.0


def test_missing_factors_reject_forward_adjust(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    _write_bars([(date(2024, 1, 2), 10.0, 10.0)])
    _load_caches()
    client = TestClient(create_app())

    qfq = client.get("/api/v1/ohlcv/1d/000001.SZ")
    assert qfq.status_code == 503
    assert qfq.json()["detail"] == "adjust factors unavailable"
    raw = client.get("/api/v1/ohlcv/1d/000001.SZ", params={"adjust": "none"})
    assert raw.status_code == 200
    assert raw.json()["bars"][0]["close"] == 10.0


def test_misaligned_factors_reject_forward_adjust(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    _write_bars([(date(2024, 1, 2), 10.0, 10.0)])
    _write_factors([(date(2024, 1, 3), 1.0)])
    _load_caches()
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ")
    assert response.status_code == 503
    assert response.json()["detail"] == "adjust factors unavailable"


def test_unknown_adjust_is_rejected(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/api/v1/ohlcv/1d/000001.SZ", params={"adjust": "hfq"})
    assert response.status_code == 422


def test_lifespan_loads_factors_for_the_default_view(tmp_path, monkeypatch) -> None:
    _seed_ohlcv(tmp_path, monkeypatch)
    clear_ohlcv_1d_cache()
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/ohlcv/1d/000001.SZ")
    assert response.status_code == 200
    assert response.json()["adjust"] == "qfq"
    assert response.json()["bars"][0]["close"] == 9.21
