from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tick.core.config import settings
from tick.market.ingest_ths_corp_actions import ingest_ths_corp_actions
from tick.market.schema import CORP_ACTION_COLUMNS, VENDOR_THS
from tick.market.ths_corp_actions_adapter import ths_corp_actions_to_canonical


def _sample_ths_corp_actions() -> pa.Table:
    # 2016-11-17 00:00 Asia/Shanghai == 2016-11-16 16:00 UTC
    return pa.table(
        {
            "thscode": ["000001.SZ"],
            "ticker": ["000001"],
            "ex_date_ms": [1479312000000],
            "dividend_per_share": [0.3],
            "per_share_bonus": [0.4],
            "allotment_ratio": [0.1],
            "allotment_price": [16.0],
            "currency": ["CNY"],
        }
    )


def test_ths_corp_actions_to_canonical_maps_fields() -> None:
    out = ths_corp_actions_to_canonical(_sample_ths_corp_actions())

    assert out.column_names == list(CORP_ACTION_COLUMNS)
    assert out["symbol"].to_pylist() == ["000001.SZ"]
    assert out["ex_date"].to_pylist() == [date(2016, 11, 17)]
    assert out["dividend_per_share"].to_pylist() == [0.3]
    assert out["bonus_per_share"].to_pylist() == [0.4]
    assert out["vendor"].to_pylist() == [VENDOR_THS]


def test_ths_corp_actions_requires_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        ths_corp_actions_to_canonical(pa.table({"thscode": ["000001.SZ"]}))


def test_ingest_ths_corp_actions_writes_canonical(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    paths = settings.paths
    paths.ensure()
    pq.write_table(_sample_ths_corp_actions(), paths.raw_ths_corp_actions)

    output = ingest_ths_corp_actions()
    assert output == paths.market_corp_actions
    table = pq.read_table(output)
    assert table.num_rows == 1
    assert table.column_names == list(CORP_ACTION_COLUMNS)
