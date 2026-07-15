"""Shared market selection and K-line fetch helpers for the Web API."""
from __future__ import annotations

from dataclasses import dataclass

from pa_agent.api.context import ApiContext
from pa_agent.config.settings import save_settings
from pa_agent.data import factory as data_factory
from pa_agent.data.base import DataSourceTransientError
from pa_agent.data.factory import default_symbol_for_kind, normalize_data_source_kind
from pa_agent.data.kline_cache import KlineCacheEntry, merge_bars_newest_first
from pa_agent.data.snapshot import INDICATOR_WARMUP_BARS


class MarketDataError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class MarketSelection:
    source: str
    symbol: str
    timeframe: str


def supported_timeframes_for_source(source: str | None) -> list[str]:
    kind = normalize_data_source_kind(source)
    data_source = data_factory.create_data_source(kind)
    return data_source.supported_timeframes()


def current_market_selection(ctx: ApiContext) -> MarketSelection:
    general = ctx.settings.general
    return MarketSelection(
        source=normalize_data_source_kind(general.last_data_source),
        symbol=(general.last_symbol or "").strip(),
        timeframe=(general.last_timeframe or "").strip(),
    )


def update_market_selection(
    ctx: ApiContext,
    *,
    source: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
) -> MarketSelection:
    current = current_market_selection(ctx)
    kind = normalize_data_source_kind(source) if source is not None else current.source
    source_changed = kind != current.source

    next_symbol = (symbol if symbol is not None else current.symbol).strip()
    if not next_symbol or (source_changed and symbol is None):
        next_symbol = default_symbol_for_kind(kind)

    timeframes = supported_timeframes_for_source(kind)
    next_timeframe = (timeframe if timeframe is not None else current.timeframe).strip()
    if not next_timeframe or next_timeframe not in timeframes:
        preferred = "1h" if "1h" in timeframes else timeframes[0]
        if timeframe is not None and next_timeframe:
            raise MarketDataError(
                422,
                f"Unsupported timeframe {next_timeframe!r} for source {kind!r}",
            )
        next_timeframe = preferred

    ctx.settings.general.last_data_source = kind  # type: ignore[assignment]
    ctx.settings.general.last_symbol = next_symbol
    ctx.settings.general.last_timeframe = next_timeframe
    if ctx.settings_path is not None:
        save_settings(ctx.settings, ctx.settings_path)
    return MarketSelection(kind, next_symbol, next_timeframe)


def fetch_and_cache_kline_data(ctx: ApiContext) -> KlineCacheEntry:
    selection = current_market_selection(ctx)
    max_bars = int(ctx.settings.general.kline_cache_max_bars)
    request_bars = min(
        max(
            int(ctx.settings.general.analysis_bar_count) + INDICATOR_WARMUP_BARS + 5,
            30,
        ),
        max_bars,
    )
    data_source = data_factory.create_data_source(selection.source)
    try:
        data_source.connect()
        data_source.subscribe(selection.symbol, selection.timeframe)
        fetched_bars = data_source.latest_snapshot(request_bars)
    except ValueError as exc:
        raise MarketDataError(422, str(exc)) from exc
    except DataSourceTransientError as exc:
        raise MarketDataError(503, str(exc)) from exc
    except Exception as exc:
        raise MarketDataError(502, f"K-line data fetch failed: {exc}") from exc
    finally:
        try:
            data_source.disconnect()
        except Exception:
            pass

    if not fetched_bars:
        raise MarketDataError(404, "Data source returned no K-line bars")

    cached = ctx.kline_cache.read(selection.source, selection.symbol, selection.timeframe)
    merged = merge_bars_newest_first(
        cached.bars if cached is not None else (),
        fetched_bars,
        max_bars=max_bars,
    )
    ctx.kline_cache.write(
        selection.source,
        selection.symbol,
        selection.timeframe,
        merged,
        max_bars=max_bars,
    )
    entry = ctx.kline_cache.read(selection.source, selection.symbol, selection.timeframe)
    if entry is None:
        raise MarketDataError(500, "K-line cache write failed")
    return entry
