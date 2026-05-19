"""MT5 data source stub — not yet implemented.

To activate: install MetaTrader5 Python package and implement each method.
See design §B.20 for the extension plan.
"""
from __future__ import annotations

# from MetaTrader5 import initialize, shutdown, copy_rates_from_pos, ...  # noqa: ERA001

from pa_agent.data.base import DataSource, KlineBar


class MT5Source(DataSource):
    """Stub implementation of DataSource for MetaTrader 5.

    All methods raise NotImplementedError until the MT5 integration is built.
    """

    def connect(self) -> None:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")

    def disconnect(self) -> None:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")

    def list_symbols(self) -> list[str]:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")

    def supported_timeframes(self) -> list[str]:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")

    def subscribe(self, symbol: str, timeframe: str) -> None:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")

    def unsubscribe(self) -> None:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")

    def latest_snapshot(self, n: int) -> list[KlineBar]:
        raise NotImplementedError("MT5 source is a stub; see design §B.20")
