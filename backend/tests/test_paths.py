from pathlib import Path

from tick.core.paths import DataPaths


def test_data_paths_layout(tmp_path: Path) -> None:
    paths = DataPaths(root=tmp_path)

    assert paths.sqlite_path == tmp_path / "db" / "tick.db"
    assert paths.market_ohlcv_1d_full == (
        tmp_path / "market" / "ohlcv" / "1d" / "full.parquet"
    )


def test_ensure_creates_first_version_dirs(tmp_path: Path) -> None:
    paths = DataPaths(root=tmp_path)
    paths.ensure()

    assert paths.db_dir.is_dir()
    assert paths.market_ohlcv_1d_dir.is_dir()
    assert not paths.sqlite_path.exists()
    assert not paths.market_ohlcv_1d_full.exists()
