import json
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from tick.core.config import settings
from tick.market.factor_cache import (
    clear_factor_cache,
    get_factor_cache,
    load_adjust_factors_into_memory,
)
from tick.market.schema import ADJUST_FACTOR_COLUMNS, VENDOR_THS


def _factor_table(day: date, factor: float) -> pa.Table:
    return pa.table(
        {
            "symbol": ["000001.SZ"],
            "trade_date": [day],
            "factor": [factor],
            "vendor": [VENDOR_THS],
        }
    ).select(list(ADJUST_FACTOR_COLUMNS))


def test_missing_file_clears_a_previous_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()
    pq.write_table(
        _factor_table(date(2024, 1, 2), 1.0),
        settings.paths.market_adjust_factors,
    )
    load_adjust_factors_into_memory()
    assert "000001.SZ" in get_factor_cache()

    settings.paths.market_adjust_factors.unlink()
    load_adjust_factors_into_memory()
    assert get_factor_cache() == {}


def test_dataset_manifest_beats_the_single_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.paths.ensure()
    day = date(2024, 1, 3)
    pq.write_table(
        _factor_table(date(2024, 1, 2), 1.0),
        settings.paths.market_adjust_factors,
    )
    partition = settings.paths.adjust_factor_partition(day.isoformat())
    partition.parent.mkdir(parents=True)
    pq.write_table(_factor_table(day, 2.0), partition)
    settings.paths.adjust_factors_dataset_manifest.write_text(
        json.dumps({"partitions": [{"trade_date": day.isoformat()}]}),
        encoding="utf-8",
    )

    clear_factor_cache()
    loaded = load_adjust_factors_into_memory()
    assert loaded["000001.SZ"].times == ["2024-01-03"]
    assert loaded["000001.SZ"].factor == [2.0]
