from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.market.instruments_cache import (
    clear_instruments_cache,
    get_instruments_cache,
    load_instruments_into_memory,
)
from tick.market.schema import INSTRUMENT_COLUMNS


def _write_sample_instruments(path) -> None:
    updated = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
    table = pa.table(
        {
            "symbol": ["600519.SH", "000300.SH"],
            "ticker": ["600519", "000300"],
            "name": ["贵州茅台", "沪深300"],
            "exchange": ["SH", "SH"],
            "asset_type": ["a-share", "a-share-index"],
            "currency": ["CNY", "CNY"],
            "list_date": [date(2001, 8, 27), date(2005, 4, 8)],
            "end_date": [None, None],
            "last_trade_date": [None, None],
            "last_delivery_date": [None, None],
            "updated_at": [updated, updated],
        }
    ).select(list(INSTRUMENT_COLUMNS))
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def test_load_instruments_into_memory_by_symbol(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()
    _write_sample_instruments(paths.market_instruments)

    cache = load_instruments_into_memory()

    assert set(cache) == {"600519.SH", "000300.SH"}
    assert cache["600519.SH"].name == "贵州茅台"
    assert cache["600519.SH"].asset_type == "a-share"
    assert cache["600519.SH"].list_date == date(2001, 8, 27)
    assert cache["000300.SH"].asset_type == "a-share-index"
    assert get_instruments_cache() is cache


def test_load_instruments_into_memory_missing_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()
    clear_instruments_cache()

    cache = load_instruments_into_memory()

    assert cache == {}
