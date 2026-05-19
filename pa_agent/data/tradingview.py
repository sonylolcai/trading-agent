"""TradingView data source using tvdatafeed."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from pa_agent.data.base import (
    DataSource,
    DataSourceTransientError,
    KlineBar,
)

logger = logging.getLogger(__name__)

# Map our timeframe strings to tvDatafeed Interval enum names
_TF_MAP: dict[str, str] = {
    "1m":  "in_1_minute",
    "3m":  "in_3_minute",
    "5m":  "in_5_minute",
    "15m": "in_15_minute",
    "30m": "in_30_minute",
    "45m": "in_45_minute",
    "1h":  "in_1_hour",
    "2h":  "in_2_hour",
    "3h":  "in_3_hour",
    "4h":  "in_4_hour",
    "1d":  "in_daily",
    "1w":  "in_weekly",
    "1M":  "in_monthly",
}


class TradingViewSource(DataSource):
    """Live K-line data from TradingView via tvdatafeed."""

    def __init__(self, username: str = "", password: str = "") -> None:
        self._username = username
        self._password = password
        self._tv = None          # tvDatafeed instance
        self._symbol: str = ""
        self._timeframe: str = ""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        try:
            from tvDatafeed import TvDatafeed  # type: ignore[import]
            if self._username and self._password:
                self._tv = TvDatafeed(self._username, self._password)
            else:
                self._tv = TvDatafeed()  # anonymous
            logger.info("TradingViewSource connected (anonymous=%s)", not self._username)
        except Exception as exc:
            raise DataSourceTransientError(f"TradingView connect failed: {exc}") from exc

    def disconnect(self) -> None:
        self._tv = None
        logger.info("TradingViewSource disconnected")

    # ── Discovery ─────────────────────────────────────────────────────────────

    def list_symbols(self) -> list[str]:
        # tvDatafeed doesn't expose a symbol list; return common defaults
        return ["XAUUSD", "BTCUSDT", "EURUSD", "GBPUSD", "NQ1!", "ES1!"]

    def supported_timeframes(self) -> list[str]:
        return list(_TF_MAP.keys())

    # ── Subscription ──────────────────────────────────────────────────────────

    def subscribe(self, symbol: str, timeframe: str) -> None:
        if timeframe not in _TF_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe!r}. Use one of {list(_TF_MAP)}")
        self._symbol = symbol
        self._timeframe = timeframe
        logger.info("TradingViewSource subscribed: %s %s", symbol, timeframe)

    def unsubscribe(self) -> None:
        self._symbol = ""
        self._timeframe = ""
        logger.info("TradingViewSource unsubscribed")

    # ── Data fetch ────────────────────────────────────────────────────────────

    def latest_snapshot(self, n: int) -> list[KlineBar]:
        """Return *n* bars newest-first; bars[0] is the forming (unclosed) bar."""
        if self._tv is None:
            raise DataSourceTransientError("Not connected — call connect() first")
        if not self._symbol or not self._timeframe:
            raise DataSourceTransientError("Not subscribed — call subscribe() first")

        try:
            from tvDatafeed import Interval  # type: ignore[import]
            interval = getattr(Interval, _TF_MAP[self._timeframe])
            # Fetch n+1 bars so we always have a forming bar at the head
            df = self._tv.get_hist(
                symbol=self._symbol,
                exchange="",          # auto-detect exchange
                interval=interval,
                n_bars=n + 1,
            )
        except Exception as exc:
            raise DataSourceTransientError(f"TradingView fetch failed: {exc}") from exc

        if df is None or df.empty:
            raise DataSourceTransientError("TradingView returned empty data")

        # df is sorted oldest-first; reverse to newest-first
        df = df.iloc[::-1].reset_index()

        bars: list[KlineBar] = []
        for i, row in enumerate(df.itertuples(index=False)):
            # The first row (i=0) is the forming bar
            ts = _row_ts(row)
            bars.append(KlineBar(
                seq=i + 1,
                ts_open=ts,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(getattr(row, "volume", 0.0)),
                closed=(i != 0),
            ))
            if len(bars) >= n:
                break

        return bars


def _row_ts(row) -> float:
    """Extract Unix timestamp from a tvDatafeed DataFrame row."""
    # The index column is named 'datetime' after reset_index
    dt = getattr(row, "datetime", None)
    if dt is None:
        return time.time()
    if hasattr(dt, "timestamp"):
        return dt.timestamp()
    # Fallback: parse string
    try:
        return datetime.fromisoformat(str(dt)).replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return time.time()
