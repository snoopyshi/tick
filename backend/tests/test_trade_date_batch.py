import math
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.adjust_factors import AdjustFactorError
from tick.market.catalog import get_capability
from tick.market.ingest_trade_date_batch import ingest_trade_date_batch
from tick.market.manifest import publish_parquet_with_manifest
from tick.market.migrate_trade_date_partitions import migrate_trade_date_partitions
from tick.market.schema import (
    ADJUST_FACTOR_COLUMNS,
    CORP_ACTION_COLUMNS,
    OHLCV_1D_COLUMNS,
)


def _bars(rows: list[tuple[str, date, float]]) -> pa.Table:
    return pa.table(
        {
            "symbol": [row[0] for row in rows],
            "trade_date": [row[1] for row in rows],
            "open": [row[2] for row in rows],
            "high": [row[2] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[2] for row in rows],
            "volume": [1.0] * len(rows),
            "amount": [row[2] for row in rows],
            "adjust": ["none"] * len(rows),
            "vendor": ["ths"] * len(rows),
            "currency": ["CNY"] * len(rows),
        }
    ).select(list(OHLCV_1D_COLUMNS))


def _events(rows: list[tuple]) -> None:
    table = pa.table(
        {
            "symbol": [row[0] for row in rows],
            "ex_date": [row[1] for row in rows],
            "dividend_per_share": [row[2] for row in rows],
            "bonus_per_share": [row[3] for row in rows],
            "allotment_ratio": [0.0] * len(rows),
            "allotment_price": [0.0] * len(rows),
            "vendor": ["ths"] * len(rows),
            "currency": ["CNY"] * len(rows),
        }
    ).select(list(CORP_ACTION_COLUMNS))
    publish_parquet_with_manifest(
        table,
        settings.paths.market_corp_actions,
        {
            "capability_id": "market.corp_actions",
            "schema_version": 1,
            "columns": list(CORP_ACTION_COLUMNS),
            "rows": table.num_rows,
            "symbols": len({row[0] for row in rows}),
            "vendor": "ths",
            "snapshot_id": "events",
            "produced_at": "2026-11-20T00:00:00Z",
            "min_date": "2024-01-02",
            "max_date": "2024-01-05",
        },
    )


def _size(trade_date: date) -> int:
    return settings.paths.ohlcv_1d_partition(trade_date.isoformat()).stat().st_size


def _factor(trade_date: date, symbol: str) -> float:
    path = settings.paths.adjust_factor_partition(trade_date.isoformat())
    table = pq.read_table(path)
    symbols = table["symbol"].to_pylist()
    factors = table["factor"].to_pylist()
    return dict(zip(symbols, factors, strict=True))[symbol]


def test_latest_day_keeps_earlier_partitions() -> None:
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    day3 = date(2024, 1, 4)
    _events([])
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day1, 10.0),
                ("000002.SZ", day1, 20.0),
                ("000001.SZ", day2, 11.0),
                ("000002.SZ", day2, 21.0),
            ]
        )
    )
    before = {
        day1: settings.paths.ohlcv_1d_partition(day1.isoformat()).stat().st_size,
        day2: settings.paths.ohlcv_1d_partition(day2.isoformat()).stat().st_size,
    }
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day3, 12.0),
                ("000002.SZ", day3, 22.0),
            ]
        )
    )
    assert _size(day1) == before[day1]
    assert _size(day2) == before[day2]
    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "ready"
    assert view.coverage is not None
    assert view.coverage.max_date == "2024-01-04"
    assert math.isclose(_factor(day3, "000001.SZ"), _factor(day2, "000001.SZ"))


def test_resubmitting_one_day_does_not_touch_others() -> None:
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    _events([])
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day1, 10.0),
                ("000002.SZ", day1, 20.0),
                ("000001.SZ", day2, 11.0),
                ("000002.SZ", day2, 21.0),
            ]
        )
    )
    day1_size = _size(day1)
    ingest_trade_date_batch(
        _bars([("000001.SZ", day2, 11.5), ("000002.SZ", day2, 21.5)])
    )
    assert _size(day1) == day1_size
    close = pq.read_table(settings.paths.ohlcv_1d_partition(day2.isoformat()))
    assert close["close"].to_pylist() == [11.5, 21.5]


def test_three_day_batch_applies_dividend_on_the_second_day() -> None:
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    day3 = date(2024, 1, 4)
    _events([("000001.SZ", day2, 1.0, 0.0)])
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day1, 10.0),
                ("000002.SZ", day1, 20.0),
                ("000001.SZ", day2, 9.0),
                ("000002.SZ", day2, 20.0),
                ("000001.SZ", day3, 9.0),
                ("000002.SZ", day3, 20.0),
            ]
        )
    )
    assert math.isclose(_factor(day1, "000001.SZ"), 1.0)
    assert math.isclose(_factor(day2, "000001.SZ"), 1 / 0.9)
    assert math.isclose(_factor(day3, "000001.SZ"), 1 / 0.9)
    assert math.isclose(_factor(day3, "000002.SZ"), 1.0)


def test_filling_a_gap_rewrites_factors_through_the_watermark() -> None:
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    day3 = date(2024, 1, 4)
    _events([("000001.SZ", day2, 1.0, 0.0)])
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day1, 10.0),
                ("000002.SZ", day1, 20.0),
                ("000001.SZ", day3, 10.0),
                ("000002.SZ", day3, 20.0),
            ]
        )
    )
    day1_factor = settings.paths.adjust_factor_partition(
        day1.isoformat()
    ).stat().st_size
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day2, 9.0),
                ("000002.SZ", day2, 20.0),
            ]
        )
    )
    assert (
        settings.paths.adjust_factor_partition(day1.isoformat()).stat().st_size
        == day1_factor
    )
    assert math.isclose(_factor(day2, "000001.SZ"), 1 / 0.9)
    assert math.isclose(_factor(day3, "000001.SZ"), 1 / 0.9)
    view = get_capability("market.adjust_factors")
    assert view is not None
    assert view.status == "ready"
    assert view.coverage is not None
    assert view.coverage.max_date == "2024-01-04"


def test_failed_batch_leaves_existing_partitions() -> None:
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    _events([("000001.SZ", day2, 0.0, -1.0)])
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day1, 10.0),
                ("000002.SZ", day1, 20.0),
            ]
        )
    )
    manifest = settings.paths.ohlcv_1d_dataset_manifest.read_bytes()
    day1_size = _size(day1)
    with pytest.raises(AdjustFactorError):
        ingest_trade_date_batch(
            _bars(
                [
                    ("000001.SZ", day2, 10.0),
                    ("000002.SZ", day2, 20.0),
                ]
            )
        )
    assert settings.paths.ohlcv_1d_dataset_manifest.read_bytes() == manifest
    assert _size(day1) == day1_size
    assert not settings.paths.ohlcv_1d_partition(day2.isoformat()).exists()


def test_query_reads_only_the_watermark_partition() -> None:
    day1 = date(2024, 1, 2)
    day2 = date(2024, 1, 3)
    _events([])
    ingest_trade_date_batch(
        _bars(
            [
                ("000001.SZ", day1, 10.0),
                ("000002.SZ", day1, 20.0),
                ("000001.SZ", day2, 11.0),
                ("000002.SZ", day2, 21.0),
            ]
        )
    )
    settings.paths.ohlcv_1d_partition(day1.isoformat()).write_bytes(b"garbage")
    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "ready"
    assert view.coverage is not None
    assert view.coverage.max_date == day2.isoformat()


def test_migration_keeps_the_single_file() -> None:
    day = date(2024, 1, 2)
    bars = _bars([("000001.SZ", day, 10.0), ("000002.SZ", day, 20.0)])
    factors = pa.table(
        {
            "symbol": ["000001.SZ", "000002.SZ"],
            "trade_date": [day, day],
            "factor": [1.0, 1.0],
            "vendor": ["ths", "ths"],
        }
    ).select(list(ADJUST_FACTOR_COLUMNS))
    common = {
        "schema_version": 1,
        "rows": 2,
        "symbols": 2,
        "vendor": "ths",
        "snapshot_id": "single",
        "produced_at": "2026-11-20T00:00:00Z",
        "min_date": "2024-01-02",
        "max_date": "2024-01-02",
    }
    publish_parquet_with_manifest(
        bars,
        settings.paths.market_ohlcv_1d,
        {
            **common,
            "capability_id": "market.ohlcv.1d",
            "columns": list(OHLCV_1D_COLUMNS),
            "adjust": "none",
        },
    )
    publish_parquet_with_manifest(
        factors,
        settings.paths.market_adjust_factors,
        {
            **common,
            "capability_id": "market.adjust_factors",
            "columns": list(ADJUST_FACTOR_COLUMNS),
        },
    )
    migrate_trade_date_partitions()
    assert settings.paths.market_ohlcv_1d.is_file()
    assert settings.paths.market_adjust_factors.is_file()
    view = get_capability("market.ohlcv.1d")
    assert view is not None
    assert view.status == "ready"
    assert view.path == "market/ohlcv/1d"
    assert settings.paths.ohlcv_1d_partition(day.isoformat()).is_file()
