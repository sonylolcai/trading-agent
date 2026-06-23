"""Small JSON cache for K-line bars."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pa_agent.config.paths import KLINE_CACHE_DIR
from pa_agent.data.base import KlineBar, normalize_kline_bar

SCHEMA_VERSION = 1
_UNSAFE_PATH_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class KlineCacheEntry:
    source: str
    symbol: str
    timeframe: str
    saved_at: str
    bars: tuple[KlineBar, ...]


def _safe_path_part(value: str) -> str:
    safe = _UNSAFE_PATH_CHARS.sub("_", str(value).strip())
    return safe.strip("._") or "_"


def _normalize_for_cache(bar: KlineBar) -> KlineBar:
    normalized = normalize_kline_bar(bar)
    if normalized.ts_open != bar.ts_open:
        normalized = replace(normalized, ts_open=bar.ts_open)
    return normalized


def _rebase_seq(bars: Iterable[KlineBar]) -> list[KlineBar]:
    rebased: list[KlineBar] = []
    closed_seq = 1
    for bar in bars:
        normalized = _normalize_for_cache(bar)
        if normalized.closed:
            rebased.append(replace(normalized, seq=closed_seq))
            closed_seq += 1
        else:
            rebased.append(replace(normalized, seq=0))
    return rebased


def merge_bars_newest_first(
    cached: Iterable[KlineBar],
    fetched: Iterable[KlineBar],
    max_bars: int,
) -> list[KlineBar]:
    """Merge cached and fetched bars by ``ts_open``; fetched bars win conflicts."""
    by_ts: dict[float, KlineBar] = {}
    for bar in cached:
        normalized = _normalize_for_cache(bar)
        by_ts[normalized.ts_open] = normalized
    for bar in fetched:
        normalized = _normalize_for_cache(bar)
        by_ts[normalized.ts_open] = normalized

    sorted_bars = sorted(by_ts.values(), key=lambda bar: bar.ts_open, reverse=True)
    return _rebase_seq(sorted_bars[:max_bars])


def _bar_to_json(bar: KlineBar) -> dict[str, object]:
    return {
        "seq": bar.seq,
        "ts_open": bar.ts_open,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "amount": bar.amount,
        "pct_chg": bar.pct_chg,
        "closed": bar.closed,
    }


def _as_number(raw: object, field: str) -> float:
    if isinstance(raw, bool):
        raise ValueError(f"{field} must be numeric")
    if isinstance(raw, int | float):
        return float(raw)
    raise ValueError(f"{field} must be numeric")


def _as_int(raw: object, field: str) -> int:
    value = _as_number(raw, field)
    if not value.is_integer():
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _bar_from_json(raw: object) -> KlineBar:
    if not isinstance(raw, dict):
        raise ValueError("bar must be an object")
    closed = raw.get("closed", True)
    if not isinstance(closed, bool):
        raise ValueError("closed must be a bool")
    pct_chg = raw.get("pct_chg")
    bar = KlineBar(
        seq=_as_int(raw["seq"], "seq"),
        ts_open=_as_number(raw["ts_open"], "ts_open"),
        open=_as_number(raw["open"], "open"),
        high=_as_number(raw["high"], "high"),
        low=_as_number(raw["low"], "low"),
        close=_as_number(raw["close"], "close"),
        volume=_as_number(raw.get("volume", 0.0), "volume"),
        amount=_as_number(raw.get("amount", 0.0), "amount"),
        pct_chg=None if pct_chg is None else _as_number(pct_chg, "pct_chg"),
        closed=closed,
    )
    return _normalize_for_cache(bar)


class KlineCacheStore:
    def __init__(self, root: Path = KLINE_CACHE_DIR) -> None:
        self.root = Path(root)

    def path_for(self, source: str, symbol: str, timeframe: str) -> Path:
        filename = f"{_safe_path_part(symbol)}_{_safe_path_part(timeframe)}.json"
        return self.root / _safe_path_part(source) / filename

    def read(self, source: str, symbol: str, timeframe: str) -> KlineCacheEntry | None:
        path = self.path_for(source, symbol, timeframe)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        if not isinstance(raw, dict):
            return None
        if raw.get("schema_version") != SCHEMA_VERSION:
            return None
        if raw.get("source") != source or raw.get("symbol") != symbol:
            return None
        if raw.get("timeframe") != timeframe:
            return None
        if not isinstance(raw.get("saved_at"), str):
            return None
        if not isinstance(raw.get("bars"), list):
            return None

        try:
            bars = tuple(_rebase_seq(_bar_from_json(bar) for bar in raw["bars"]))
        except (KeyError, TypeError, ValueError):
            return None

        return KlineCacheEntry(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            saved_at=raw["saved_at"],
            bars=bars,
        )

    def write(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        bars: Iterable[KlineBar],
        *,
        max_bars: int,
    ) -> Path:
        path = self.path_for(source, symbol, timeframe)
        merged = merge_bars_newest_first((), bars, max_bars=max_bars)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "bars": [_bar_to_json(bar) for bar in merged],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
