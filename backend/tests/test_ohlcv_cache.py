from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.market.ohlcv_cache import (
    clear_ohlcv_1d_cache,
    get_ohlcv_1d_cache,
    load_ohlcv_1d_into_memory,
)
from tick.market.schema import OHLCV_1D_COLUMNS, VENDOR_THS


def _write_sample_ohlcv(path) -> None:
    table = pa.table(
        {
            "symbol": ["000002.SZ", "000001.SZ", "000001.SZ"],
            "trade_date": [date(2016, 11, 18), date(2016, 11, 18), date(2016, 11, 17)],
            "open": [1.0, 9.21, 9.22],
            "high": [1.1, 9.21, 9.22],
            "low": [0.9, 9.16, 9.18],
            "close": [1.05, 9.18, 9.21],
            "volume": [100.0, 51759734.0, 50532402.0],
            "amount": [1000.0, 475289972.51, 464611128.37],
            "adjust": ["none", "none", "none"],
            "vendor": [VENDOR_THS, VENDOR_THS, VENDOR_THS],
            "currency": ["CNY", "CNY", "CNY"],
        }
    ).select(list(OHLCV_1D_COLUMNS))
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def test_load_ohlcv_1d_into_memory_groups_by_symbol(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()
    _write_sample_ohlcv(paths.market_ohlcv_1d)

    cache = load_ohlcv_1d_into_memory()

    assert set(cache) == {"000001.SZ", "000002.SZ"}
    assert cache["000001.SZ"].times == ["2016-11-17", "2016-11-18"]
    assert cache["000001.SZ"].close == [9.21, 9.18]
    assert len(cache["000002.SZ"]) == 1
    assert get_ohlcv_1d_cache() is cache


def test_load_ohlcv_1d_into_memory_missing_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()
    clear_ohlcv_1d_cache()

    cache = load_ohlcv_1d_into_memory()

    assert cache == {}
