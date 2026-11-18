import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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
    def market_ohlcv_1d_dir(self) -> Path:
        return self.root / "market" / "ohlcv" / "1d"

    @property
    def market_ohlcv_1d_full(self) -> Path:
        """Ten-year full-market daily OHLCV Parquet file."""
        return self.market_ohlcv_1d_dir / "full.parquet"

    def ensure(self) -> None:
        """Create the first-version data directories if missing."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.market_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "data ready: root=%s sqlite=%s ohlcv_1d=%s (exists=%s)",
            self.root,
            self.sqlite_path,
            self.market_ohlcv_1d_full,
            self.market_ohlcv_1d_full.exists(),
        )
