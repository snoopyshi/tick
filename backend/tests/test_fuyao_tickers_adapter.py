from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.fuyao_tickers_adapter import (
    fuyao_items_to_raw_table,
    fuyao_tickers_to_canonical,
)
from tick.market.ingest_fuyao_tickers import (
    _parse_asset_types,
    ingest_fuyao_tickers,
)
from tick.market.schema import (
    DEFAULT_TICKER_ASSET_TYPES,
    INSTRUMENT_COLUMNS,
    VENDOR_SYMBOL_MAP_COLUMNS,
    VENDOR_THS,
)


def _sample_items() -> list[dict]:
    return [
        {
            "thscode": "600519.SH",
            "ticker": "600519",
            "name": "贵州茅台",
            "exchange": "SH",
            "asset_type": "a-share",
            "currency": "CNY",
            "list_date": "2001-08-27",
            "end_date": None,
            "last_trade_date": None,
            "last_delivery_date": None,
        },
        {
            "thscode": "000001.SZ",
            "ticker": "000001",
            "name": "平安银行",
            "exchange": "SZ",
            "asset_type": "a-share",
            "currency": "CNY",
            "list_date": "1991-04-03",
            "end_date": None,
            "last_trade_date": None,
            "last_delivery_date": None,
        },
        {
            "thscode": "000300.SH",
            "ticker": "000300",
            "name": "沪深300",
            "exchange": "SH",
            "asset_type": "a-share-index",
            "currency": "CNY",
            "list_date": "2005-04-08",
            "end_date": None,
            "last_trade_date": None,
            "last_delivery_date": None,
        },
    ]


def test_fuyao_items_to_raw_table_and_canonical() -> None:
    snapshot_ms = 1_716_105_600_000
    raw = fuyao_items_to_raw_table(_sample_items(), snapshot_ms=snapshot_ms)
    assert raw.num_rows == 3
    assert "thscode" in raw.column_names
    assert raw["snapshot_ms"].to_pylist() == [snapshot_ms, snapshot_ms, snapshot_ms]

    instruments, vendor_map = fuyao_tickers_to_canonical(raw)
    assert instruments.column_names == list(INSTRUMENT_COLUMNS)
    assert vendor_map.column_names == list(VENDOR_SYMBOL_MAP_COLUMNS)
    assert instruments["symbol"].to_pylist() == [
        "600519.SH",
        "000001.SZ",
        "000300.SH",
    ]
    assert instruments["ticker"].to_pylist() == ["600519", "000001", "000300"]
    assert instruments["name"].to_pylist() == ["贵州茅台", "平安银行", "沪深300"]
    assert instruments["asset_type"].to_pylist() == [
        "a-share",
        "a-share",
        "a-share-index",
    ]
    assert instruments["list_date"].to_pylist() == [
        date(2001, 8, 27),
        date(1991, 4, 3),
        date(2005, 4, 8),
    ]
    assert instruments["end_date"].to_pylist() == [None, None, None]
    assert instruments["updated_at"].to_pylist() == [
        datetime.fromtimestamp(snapshot_ms / 1000.0, tz=UTC),
        datetime.fromtimestamp(snapshot_ms / 1000.0, tz=UTC),
        datetime.fromtimestamp(snapshot_ms / 1000.0, tz=UTC),
    ]
    assert vendor_map["vendor"].to_pylist() == [VENDOR_THS, VENDOR_THS, VENDOR_THS]
    assert vendor_map["vendor_symbol"].to_pylist() == [
        "600519.SH",
        "000001.SZ",
        "000300.SH",
    ]
    assert vendor_map["symbol"].to_pylist() == [
        "600519.SH",
        "000001.SZ",
        "000300.SH",
    ]
    assert vendor_map["is_primary"].to_pylist() == [True, True, True]


def test_default_ticker_asset_types_include_index() -> None:
    assert DEFAULT_TICKER_ASSET_TYPES == ("a-share", "a-share-index")
    assert _parse_asset_types(",".join(DEFAULT_TICKER_ASSET_TYPES)) == [
        "a-share",
        "a-share-index",
    ]


def test_fuyao_tickers_to_canonical_requires_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        fuyao_tickers_to_canonical(pa.table({"thscode": ["600519.SH"]}))


def test_ingest_fuyao_tickers_from_raw_no_fetch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()

    raw = fuyao_items_to_raw_table(_sample_items(), snapshot_ms=1_700_000_000_000)
    pq.write_table(raw, paths.raw_ths_tickers)

    instruments_path, vendor_map_path = ingest_fuyao_tickers(fetch=False)
    assert instruments_path == paths.market_instruments
    assert vendor_map_path == paths.market_vendor_symbol_map
    assert instruments_path.is_file()
    assert vendor_map_path.is_file()

    instruments = pq.read_table(instruments_path)
    vendor_map = pq.read_table(vendor_map_path)
    assert instruments.num_rows == 3
    assert vendor_map.num_rows == 3
    assert instruments.column_names == list(INSTRUMENT_COLUMNS)
    assert instruments["asset_type"].to_pylist() == [
        "a-share",
        "a-share",
        "a-share-index",
    ]
    assert vendor_map["vendor"].to_pylist() == [VENDOR_THS, VENDOR_THS, VENDOR_THS]
