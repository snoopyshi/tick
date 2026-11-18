import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Vendor snapshot filenames (keep as-is under raw/).
RAW_THS_OHLCV_1D_FILENAME = "a_share_daily_k_1d_none_10y_20261117.parquet"
RAW_THS_CORP_ACTIONS_FILENAME = (
    "a_share_adjustment_factors_event_none_all_20261117.parquet"
)
RAW_THS_TICKERS_FILENAME = "tickers.parquet"
# Stable canonical filenames used by strategies / backtests / UI.
MARKET_OHLCV_1D_FILENAME = "a_share_daily_k_1d.parquet"
MARKET_CORP_ACTIONS_FILENAME = "a_share_corp_actions.parquet"
MARKET_INSTRUMENTS_FILENAME = "instruments.parquet"
MARKET_VENDOR_SYMBOL_MAP_FILENAME = "vendor_symbol_map.parquet"


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
    def raw_ths_corp_actions_dir(self) -> Path:
        return self.root / "raw" / "ths" / "corp_actions"

    @property
    def raw_ths_corp_actions(self) -> Path:
        """Tonghuashun original corporate-action / ex-date events."""
        return self.raw_ths_corp_actions_dir / RAW_THS_CORP_ACTIONS_FILENAME

    @property
    def market_ohlcv_1d_dir(self) -> Path:
        return self.root / "market" / "ohlcv" / "1d"

    @property
    def market_ohlcv_1d(self) -> Path:
        """Canonical A-share daily OHLCV parquet for app use."""
        return self.market_ohlcv_1d_dir / MARKET_OHLCV_1D_FILENAME

    @property
    def market_corp_actions_dir(self) -> Path:
        return self.root / "market" / "corp_actions"

    @property
    def market_corp_actions(self) -> Path:
        """Canonical corporate-action events for app use."""
        return self.market_corp_actions_dir / MARKET_CORP_ACTIONS_FILENAME

    @property
    def raw_ths_tickers_dir(self) -> Path:
        return self.root / "raw" / "ths" / "tickers"

    @property
    def raw_ths_tickers(self) -> Path:
        """THS ticker-list snapshot via Fuyao API (vendor field names)."""
        return self.raw_ths_tickers_dir / RAW_THS_TICKERS_FILENAME

    @property
    def market_instruments_dir(self) -> Path:
        return self.root / "market" / "instruments"

    @property
    def market_instruments(self) -> Path:
        """Canonical instrument master parquet."""
        return self.market_instruments_dir / MARKET_INSTRUMENTS_FILENAME

    @property
    def market_vendor_symbol_map(self) -> Path:
        """Canonical vendor → system symbol map parquet."""
        return self.market_instruments_dir / MARKET_VENDOR_SYMBOL_MAP_FILENAME

    def ensure(self) -> None:
        """Create the first-version data directories if missing."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_corp_actions_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_tickers_dir.mkdir(parents=True, exist_ok=True)
        self.market_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        self.market_corp_actions_dir.mkdir(parents=True, exist_ok=True)
        self.market_instruments_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "data ready: root=%s ohlcv_1d=%s (exists=%s) corp_actions=%s "
            "(exists=%s) instruments=%s (exists=%s)",
            self.root,
            self.market_ohlcv_1d,
            self.market_ohlcv_1d.exists(),
            self.market_corp_actions,
            self.market_corp_actions.exists(),
            self.market_instruments,
            self.market_instruments.exists(),
        )
