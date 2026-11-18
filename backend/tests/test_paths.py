from pathlib import Path

from tick.core.paths import (
    MARKET_OHLCV_1D_FILENAME,
    RAW_THS_OHLCV_1D_FILENAME,
    DataPaths,
)


def test_data_paths_layout(tmp_path: Path) -> None:
    paths = DataPaths(root=tmp_path)

    assert paths.sqlite_path == tmp_path / "db" / "tick.db"
    assert paths.raw_ths_ohlcv_1d == (
        tmp_path / "raw" / "ths" / "ohlcv" / "1d" / RAW_THS_OHLCV_1D_FILENAME
    )
    assert paths.market_ohlcv_1d == (
        tmp_path / "market" / "ohlcv" / "1d" / MARKET_OHLCV_1D_FILENAME
    )


def test_ensure_creates_first_version_dirs(tmp_path: Path) -> None:
    paths = DataPaths(root=tmp_path)
    paths.ensure()

    assert paths.db_dir.is_dir()
    assert paths.raw_ths_ohlcv_1d_dir.is_dir()
    assert paths.market_ohlcv_1d_dir.is_dir()
    assert not paths.sqlite_path.exists()
    assert not paths.raw_ths_ohlcv_1d.exists()
    assert not paths.market_ohlcv_1d.exists()
