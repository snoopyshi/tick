import json
import math
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.schema import ADJUST_FACTOR_COLUMNS, OHLCV_1D_COLUMNS, VENDOR_THS
from tick.research import ResearchDataError, daily_bars


def _use_data_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()


def _bars(rows: list[tuple[date, float]]) -> pa.Table:
    return pa.table(
        {
            "symbol": ["000001.SZ"] * len(rows),
            "trade_date": [row[0] for row in rows],
            "open": [row[1] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[1] for row in rows],
            "close": [row[1] for row in rows],
            "volume": [float(index + 1) for index in range(len(rows))],
            "amount": [row[1] * 10 for row in rows],
            "adjust": ["none"] * len(rows),
            "vendor": [VENDOR_THS] * len(rows),
            "currency": ["CNY"] * len(rows),
        }
    ).select(list(OHLCV_1D_COLUMNS))


def _factors(rows: list[tuple[date, float]]) -> pa.Table:
    return pa.table(
        {
            "symbol": ["000001.SZ"] * len(rows),
            "trade_date": [row[0] for row in rows],
            "factor": [row[1] for row in rows],
            "vendor": [VENDOR_THS] * len(rows),
        }
    ).select(list(ADJUST_FACTOR_COLUMNS))


def test_forward_adjusted_bars_use_the_last_factor(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    pq.write_table(
        _bars([(day1, 10.0), (day2, 9.0)]),
        settings.paths.market_ohlcv_1d,
    )
    pq.write_table(
        _factors([(day1, 1.0), (day2, 1 / 0.9)]),
        settings.paths.market_adjust_factors,
    )

    table = daily_bars("000001.SZ")
    assert table.column_names == [
        "symbol",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    ]
    assert math.isclose(table["close"][0].as_py(), 9.0)
    assert table["close"][1].as_py() == 9.0
    assert table["volume"][0].as_py() == 1.0
    assert table["amount"][0].as_py() == 100.0


def test_adjust_none_returns_raw_prices(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    pq.write_table(
        _bars([(day1, 10.0), (day2, 9.0)]),
        settings.paths.market_ohlcv_1d,
    )
    pq.write_table(
        _factors([(day1, 1.0), (day2, 1 / 0.9)]),
        settings.paths.market_adjust_factors,
    )

    table = daily_bars("000001.SZ", adjust="none")
    assert table["close"].to_pylist() == [10.0, 9.0]


def test_unknown_symbol_is_an_empty_table(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    pq.write_table(
        _bars([(date(2024, 1, 2), 10.0)]),
        settings.paths.market_ohlcv_1d,
    )

    table = daily_bars("999999.SH")
    assert table.num_rows == 0
    assert table.column_names[0] == "symbol"
    assert "close" in table.column_names


def test_missing_factors_raise(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    pq.write_table(
        _bars([(date(2024, 1, 2), 10.0)]),
        settings.paths.market_ohlcv_1d,
    )

    with pytest.raises(ResearchDataError, match="adjust factors unavailable"):
        daily_bars("000001.SZ")


def test_misaligned_factors_raise(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    pq.write_table(
        _bars([(date(2024, 1, 2), 10.0)]),
        settings.paths.market_ohlcv_1d,
    )
    pq.write_table(
        _factors([(date(2024, 1, 3), 1.0)]),
        settings.paths.market_adjust_factors,
    )

    with pytest.raises(ResearchDataError, match="adjust factors unavailable"):
        daily_bars("000001.SZ")


def test_manifest_ignores_the_single_file(tmp_path, monkeypatch) -> None:
    _use_data_dir(tmp_path, monkeypatch)
    day = date(2024, 1, 2)
    pq.write_table(_bars([(day, 1.0)]), settings.paths.market_ohlcv_1d)
    partition = settings.paths.ohlcv_1d_partition(day.isoformat())
    partition.parent.mkdir(parents=True)
    pq.write_table(_bars([(day, 10.0)]), partition)
    settings.paths.ohlcv_1d_dataset_manifest.write_text(
        json.dumps({"partitions": [{"trade_date": day.isoformat()}]}),
        encoding="utf-8",
    )
    pq.write_table(_factors([(day, 1.0)]), settings.paths.market_adjust_factors)

    table = daily_bars("000001.SZ")
    assert table["close"].to_pylist() == [10.0]
