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
RAW_THS_CALENDAR_FILENAME = "trading_days.parquet"
# Stable canonical filenames used by strategies / backtests / UI.
MARKET_OHLCV_1D_FILENAME = "a_share_daily_k_1d.parquet"
MARKET_CORP_ACTIONS_FILENAME = "a_share_corp_actions.parquet"
MARKET_INSTRUMENTS_FILENAME = "instruments.parquet"
MARKET_VENDOR_SYMBOL_MAP_FILENAME = "vendor_symbol_map.parquet"
MARKET_ADJUST_FACTORS_FILENAME = "a_share_adjust_factors.parquet"
MARKET_CALENDAR_FILENAME = "a_share_trading_days.parquet"


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
    def raw_ths_calendar_dir(self) -> Path:
        return self.root / "raw" / "ths" / "calendar"

    @property
    def raw_ths_calendar(self) -> Path:
        """THS A-share trading-day snapshot via Fuyao."""
        return self.raw_ths_calendar_dir / RAW_THS_CALENDAR_FILENAME

    @property
    def market_calendar_dir(self) -> Path:
        return self.root / "market" / "calendar"

    @property
    def market_calendar(self) -> Path:
        """Canonical A-share trading days."""
        return self.market_calendar_dir / MARKET_CALENDAR_FILENAME

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

    @property
    def market_adjust_factors_dir(self) -> Path:
        return self.root / "market" / "adjust_factors"

    @property
    def market_adjust_factors(self) -> Path:
        """Canonical daily backward-adjust factors."""
        return self.market_adjust_factors_dir / MARKET_ADJUST_FACTORS_FILENAME

    @property
    def ohlcv_1d_dataset_manifest(self) -> Path:
        """Trade-date partitioned daily bars catalog."""
        return self.market_ohlcv_1d_dir / "manifest.json"

    def ohlcv_1d_partition(self, trade_date: str) -> Path:
        """One trade date of unadjusted daily bars."""
        return self.market_ohlcv_1d_dir / f"trade_date={trade_date}" / "part.parquet"

    @property
    def adjust_factors_dataset_manifest(self) -> Path:
        """Trade-date partitioned adjust-factor catalog."""
        return self.market_adjust_factors_dir / "manifest.json"

    def adjust_factor_partition(self, trade_date: str) -> Path:
        """One trade date of backward-adjust factors."""
        return (
            self.market_adjust_factors_dir / f"trade_date={trade_date}" / "part.parquet"
        )

    def ensure(self) -> None:
        """Create the first-version data directories if missing."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_corp_actions_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_tickers_dir.mkdir(parents=True, exist_ok=True)
        self.raw_ths_calendar_dir.mkdir(parents=True, exist_ok=True)
        self.market_calendar_dir.mkdir(parents=True, exist_ok=True)
        self.market_ohlcv_1d_dir.mkdir(parents=True, exist_ok=True)
        self.market_corp_actions_dir.mkdir(parents=True, exist_ok=True)
        self.market_instruments_dir.mkdir(parents=True, exist_ok=True)
        self.market_adjust_factors_dir.mkdir(parents=True, exist_ok=True)
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
