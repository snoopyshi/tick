import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Vendor snapshot filename (keep as-is under raw/).
RAW_THS_OHLCV_1D_FILENAME = "a_share_daily_k_1d_none_10y_20261117.parquet"
# Stable canonical filename used by strategies / backtests.
MARKET_OHLCV_1D_FILENAME = "a_share_daily_k_1d.parquet"


@dataclass(frozen=True, slots=True)
class DataPaths:
    """Resolved locations under ``DATA_DIR``."""

    root: Path

    @property
    def db_dir(self) -> Path:
        return self.root / "db"

    @property
    def sqlite_path(self) -> Path:
        return self.db_dir / "tick.db"

    @property
    def raw_ths_ohlcv_1d_dir(self) -> Path:
        return self.root / "raw" / "ths" / "ohlcv" / "1d"

    @property
    def raw_ths_ohlcv_1d(self) -> Path:
        """Tonghuashun original daily OHLCV parquet."""
        return self.raw_ths_ohlcv_1d_dir / RAW_THS_OHLCV_1D_FILENAME

    @property
    def market_ohlcv_1d_dir(self) -> Path:
        return self.root / "market" / "ohlcv" / "1d"

    @property
    def market_ohlcv_1d(self) -> Path:
        """Canonical A-share daily OHLCV parquet for app use."""
        return self.market_ohlcv_1d_dir / MARKET_OHLCV_1D_FILENAME

    def ensure(self) -> None:
        """Create the first-version data directories if missing."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        self.market_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "data ready: root=%s raw_ths=%s (exists=%s) market_ohlcv_1d=%s (exists=%s)",
            self.root,
            self.raw_ths_ohlcv_1d,
            self.raw_ths_ohlcv_1d.exists(),
            self.market_ohlcv_1d,
            self.market_ohlcv_1d.exists(),
        )
