from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.catalog import get_capability
from tick.market.fuyao_calendar_adapter import (
    shanghai_midnight_ms,
    trading_days_to_canonical,
    trading_days_to_raw,
)
from tick.market.ingest_fuyao_calendar import ingest_fuyao_calendar
from tick.market.schema import TRADING_CALENDAR_COLUMNS


def test_shanghai_midnight_matches_the_documented_instant() -> None:
    assert shanghai_midnight_ms(date(2025, 5, 23)) == 1747929600000


def test_canonical_calendar_sorts_and_checks_the_stamp() -> None:
    raw = trading_days_to_raw(
        [
            {"date_ms": shanghai_midnight_ms(date(2024, 1, 3)), "date": "20240103"},
            {"date_ms": shanghai_midnight_ms(date(2024, 1, 2)), "date": "20240102"},
        ],
        snapshot_ms=9,
    )
    table = trading_days_to_canonical(raw)
    assert table.column_names == list(TRADING_CALENDAR_COLUMNS)
    assert table["trade_date"].to_pylist() == [date(2024, 1, 2), date(2024, 1, 3)]
    assert table["vendor"].to_pylist() == ["ths", "ths"]


def test_mismatched_stamp_is_rejected() -> None:
    raw = trading_days_to_raw(
        [{"date_ms": 1, "date": "20240102"}],
        snapshot_ms=9,
    )
    with pytest.raises(ValueError, match="Shanghai midnight"):
        trading_days_to_canonical(raw)


def test_no_fetch_publishes_a_ready_calendar(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()
    raw = trading_days_to_raw(
        [
            {"date_ms": shanghai_midnight_ms(date(2024, 1, 2)), "date": "20240102"},
            {"date_ms": shanghai_midnight_ms(date(2024, 1, 3)), "date": "20240103"},
        ],
        snapshot_ms=42,
    )
    pq.write_table(raw, settings.paths.raw_ths_calendar)

    ingest_fuyao_calendar(fetch=False)
    table = pq.read_table(settings.paths.market_calendar)
    assert table["trade_date"].to_pylist() == [date(2024, 1, 2), date(2024, 1, 3)]

    view = get_capability("market.trading_calendar")
    assert view is not None
    assert view.status == "ready"
    assert view.coverage is not None
    assert view.coverage.rows == 2
    assert view.coverage.symbols == 0
    assert view.coverage.min_date == "2024-01-02"
    assert view.coverage.max_date == "2024-01-03"
    assert view.coverage.snapshot_id == "42"


def test_failed_conversion_leaves_the_canonical_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()
    raw = pa.table(
        {
            "date_ms": [1],
            "date": ["20240102"],
            "snapshot_ms": [9],
        }
    )
    pq.write_table(raw, settings.paths.raw_ths_calendar)
    settings.paths.market_calendar.write_bytes(b"keep")

    with pytest.raises(ValueError, match="Shanghai midnight"):
        ingest_fuyao_calendar(fetch=False)
    assert settings.paths.market_calendar.read_bytes() == b"keep"
