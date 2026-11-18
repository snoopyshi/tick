from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.ingest_ths import ingest_ths_daily
from tick.market.schema import OHLCV_1D_COLUMNS, VENDOR_THS
from tick.market.ths_adapter import ths_daily_to_canonical


def _sample_ths_table() -> pa.Table:
    # 2016-11-17 00:00 Asia/Shanghai == 2016-11-16 16:00 UTC
    return pa.table(
        {
            "thscode": ["000001.SZ", "000001.SZ"],
            "currency": ["CNY", "CNY"],
            "interval": ["1d", "1d"],
            "adjusted": ["none", "none"],
            "date_ms": [1479312000000, 1479398400000],
            "open_price": [9.22, 9.21],
            "high_price": [9.22, 9.21],
            "low_price": [9.18, 9.16],
            "close_price": [9.21, 9.18],
            "volume": [50532402.0, 51759734.0],
            "turnover": [4.646111e8, 4.752900e8],
        }
    )


def test_ths_daily_to_canonical_maps_fields() -> None:
    out = ths_daily_to_canonical(_sample_ths_table())

    assert out.column_names == list(OHLCV_1D_COLUMNS)
    assert out["symbol"].to_pylist() == ["000001.SZ", "000001.SZ"]
    assert out["trade_date"].to_pylist() == [date(2016, 11, 17), date(2016, 11, 18)]
    assert out["open"].to_pylist() == [9.22, 9.21]
    assert out["amount"].to_pylist() == [4.646111e8, 4.752900e8]
    assert out["adjust"].to_pylist() == ["none", "none"]
    assert out["vendor"].to_pylist() == [VENDOR_THS, VENDOR_THS]


def test_ths_daily_to_canonical_requires_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        ths_daily_to_canonical(pa.table({"thscode": ["000001.SZ"]}))


def test_ingest_ths_daily_writes_canonical_parquet(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()

    raw = paths.raw_ths_ohlcv_1d
    pq.write_table(_sample_ths_table(), raw)

    output = ingest_ths_daily()
    assert output == paths.market_ohlcv_1d
    assert output.is_file()

    table = pq.read_table(output)
    assert table.num_rows == 2
    assert table.column_names == list(OHLCV_1D_COLUMNS)
    assert table["vendor"].to_pylist() == [VENDOR_THS, VENDOR_THS]
