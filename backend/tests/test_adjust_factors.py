import math
import sys
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.adjust_factors import AdjustFactorError, compute_adjust_factors
from tick.market.catalog import get_capability
from tick.market.ingest_adjust_factors import main
from tick.market.ingest_ths import ingest_ths_daily
from tick.market.ingest_ths_corp_actions import ingest_ths_corp_actions
from tick.market.schema import ADJUST_FACTOR_COLUMNS, CORP_ACTION_COLUMNS


def _bars(rows: list[tuple[str, date, float]]) -> pa.Table:
    return pa.table(
        {
            "symbol": [row[0] for row in rows],
            "trade_date": [row[1] for row in rows],
            "close": [row[2] for row in rows],
        }
    )


def _events(rows: list[tuple]) -> pa.Table:
    return pa.table(
        {
            "symbol": [row[0] for row in rows],
            "ex_date": [row[1] for row in rows],
            "dividend_per_share": [row[2] for row in rows],
            "bonus_per_share": [row[3] for row in rows],
            "allotment_ratio": [row[4] for row in rows],
            "allotment_price": [row[5] for row in rows],
            "vendor": ["ths"] * len(rows),
            "currency": ["CNY"] * len(rows),
        }
    ).select(list(CORP_ACTION_COLUMNS))


def test_cash_dividend_scales_factor_from_ex_date() -> None:
    bars = _bars(
        [
            ("000001.SZ", date(2024, 1, 2), 10.0),
            ("000001.SZ", date(2024, 1, 3), 9.0),
        ]
    )
    events = _events([("000001.SZ", date(2024, 1, 3), 1.0, 0.0, 0.0, 0.0)])
    result = compute_adjust_factors(bars, events)
    factors = result.table["factor"].to_pylist()
    assert math.isclose(factors[0], 1.0)
    assert math.isclose(factors[1], 1 / 0.9)
    assert result.events_applied == 1
    last = factors[-1]
    qfq = [
        close * factor / last
        for close, factor in zip([10.0, 9.0], factors, strict=True)
    ]
    assert math.isclose(qfq[0], 9.0)
    assert math.isclose(qfq[1], 9.0)


def test_same_day_events_are_combined_once() -> None:
    bars = _bars(
        [
            ("603883.SH", date(2024, 6, 26), 10.0),
            ("603883.SH", date(2024, 6, 27), 8.0),
        ]
    )
    combined = _events(
        [
            ("603883.SH", date(2024, 6, 27), 0.16, 0.0, 0.0, 0.0),
            ("603883.SH", date(2024, 6, 27), 0.5, 0.3, 0.0, 0.0),
        ]
    )
    separate_sum = _events(
        [("603883.SH", date(2024, 6, 27), 0.66, 0.3, 0.0, 0.0)]
    )
    left = compute_adjust_factors(bars, combined)
    right = compute_adjust_factors(bars, separate_sum)
    assert left.table["factor"].to_pylist() == right.table["factor"].to_pylist()
    assert left.events_applied == 2


def test_identical_rows_are_counted_once() -> None:
    bars = _bars(
        [
            ("000601.SZ", date(2024, 1, 2), 10.0),
            ("000601.SZ", date(2024, 1, 3), 9.0),
        ]
    )
    duplicated = _events(
        [
            ("000601.SZ", date(2024, 1, 3), 1.0, 0.0, 0.0, 0.0),
            ("000601.SZ", date(2024, 1, 3), 1.0, 0.0, 0.0, 0.0),
        ]
    )
    once = _events([("000601.SZ", date(2024, 1, 3), 1.0, 0.0, 0.0, 0.0)])
    assert (
        compute_adjust_factors(bars, duplicated).table["factor"].to_pylist()
        == compute_adjust_factors(bars, once).table["factor"].to_pylist()
    )


def test_out_of_window_events_leave_factor_at_one() -> None:
    bars = _bars(
        [
            ("000001.SZ", date(2024, 1, 2), 10.0),
            ("000001.SZ", date(2024, 1, 3), 10.0),
        ]
    )
    events = _events(
        [
            ("000001.SZ", date(2020, 1, 1), 1.0, 0.0, 0.0, 0.0),
            ("000001.SZ", date(2024, 1, 2), 1.0, 0.0, 0.0, 0.0),
            ("000001.SZ", date(2024, 1, 4), 1.0, 0.0, 0.0, 0.0),
            ("000001.SZ", date(2024, 1, 3), 0.0, 0.0, 0.0, 0.0),
            ("999999.SZ", date(2024, 1, 3), 1.0, 0.0, 0.0, 0.0),
        ]
    )
    result = compute_adjust_factors(bars, events)
    assert result.table["factor"].to_pylist() == [1.0, 1.0]
    assert result.events_before_window == 2
    assert result.events_after_window == 1
    assert result.events_zero == 1
    assert result.events_no_bars == 1
    assert result.events_applied == 0
    assert (
        result.events_before_window
        + result.events_after_window
        + result.events_zero
        + result.events_no_bars
        + result.events_applied
        == 5
    )


def test_symbol_without_events_stays_at_one_and_keys_match() -> None:
    bars = _bars(
        [
            ("000002.SZ", date(2024, 1, 3), 5.0),
            ("000001.SZ", date(2024, 1, 2), 10.0),
        ]
    )
    result = compute_adjust_factors(bars, _events([]))
    assert result.table.column_names == list(ADJUST_FACTOR_COLUMNS)
    assert result.table["symbol"].to_pylist() == ["000001.SZ", "000002.SZ"]
    assert result.table["factor"].to_pylist() == [1.0, 1.0]
    assert result.table["vendor"].to_pylist() == ["ths", "ths"]


def test_non_positive_denominator_raises() -> None:
    bars = _bars(
        [
            ("000001.SZ", date(2024, 1, 2), 10.0),
            ("000001.SZ", date(2024, 1, 3), 10.0),
        ]
    )
    events = _events([("000001.SZ", date(2024, 1, 3), 0.0, -1.0, 0.0, 0.0)])
    with pytest.raises(AdjustFactorError):
        compute_adjust_factors(bars, events)


def _install_ready_inputs() -> None:
    paths = settings.paths
    paths.ensure()
    raw_bars = pa.table(
        {
            "thscode": ["000001.SZ", "000001.SZ"],
            "currency": ["CNY", "CNY"],
            "interval": ["1d", "1d"],
            "adjusted": ["none", "none"],
            "date_ms": [1704124800000, 1704211200000],
            "open_price": [10.0, 9.0],
            "high_price": [10.0, 9.0],
            "low_price": [10.0, 9.0],
            "close_price": [10.0, 9.0],
            "volume": [1.0, 1.0],
            "turnover": [10.0, 9.0],
        }
    )
    pq.write_table(raw_bars, paths.raw_ths_ohlcv_1d)
    raw_events = pa.table(
        {
            "thscode": ["000001.SZ"],
            "ticker": ["000001"],
            "ex_date_ms": [1704211200000],
            "dividend_per_share": [1.0],
            "per_share_bonus": [0.0],
            "allotment_ratio": [0.0],
            "allotment_price": [0.0],
            "currency": ["CNY"],
        }
    )
    pq.write_table(raw_events, paths.raw_ths_corp_actions)
    ingest_ths_daily()
    ingest_ths_corp_actions()


def test_dependency_not_ready_exits_without_file(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["tick-ingest-adjust-factors"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "market.ohlcv.1d" in capsys.readouterr().err
    assert not settings.paths.market_adjust_factors.exists()


def test_failed_compute_does_not_replace_existing_file() -> None:
    _install_ready_inputs()
    target = settings.paths.market_adjust_factors
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"keep")
    events = pq.read_table(settings.paths.market_corp_actions)
    bonus = pa.array([-1.0], type=pa.float64())
    replaced = events.set_column(
        events.schema.get_field_index("bonus_per_share"),
        "bonus_per_share",
        bonus,
    )
    pq.write_table(replaced, settings.paths.market_corp_actions)
    # Manifest still describes the previous file, so the dependency is invalid
    # until rewritten. Rewrite the manifest by ingesting the bad raw instead.
    raw = pq.read_table(settings.paths.raw_ths_corp_actions)
    raw = raw.set_column(
        raw.schema.get_field_index("per_share_bonus"),
        "per_share_bonus",
        pa.array([-1.0], type=pa.float64()),
    )
    pq.write_table(raw, settings.paths.raw_ths_corp_actions)
    ingest_ths_corp_actions()
    assert get_capability("market.corp_actions").status == "ready"

    from tick.market.ingest_adjust_factors import ingest_adjust_factors

    with pytest.raises(AdjustFactorError):
        ingest_adjust_factors()
    assert target.read_bytes() == b"keep"


def test_ingest_writes_ready_factors_with_stable_size() -> None:
    _install_ready_inputs()
    from tick.market.ingest_adjust_factors import ingest_adjust_factors

    first = ingest_adjust_factors()
    first_size = first.stat().st_size
    table = pq.read_table(first)
    assert table.column_names == list(ADJUST_FACTOR_COLUMNS)
    assert math.isclose(table["factor"].to_pylist()[1], 1 / 0.9)
    view = get_capability("market.adjust_factors")
    assert view is not None
    assert view.status == "ready"
    assert view.coverage is not None
    assert view.coverage.events_applied == 1
    assert view.coverage.snapshot_id.startswith("derived:")

    second = ingest_adjust_factors()
    assert second.stat().st_size == first_size
    assert pq.read_table(second)["factor"].to_pylist() == table["factor"].to_pylist()
