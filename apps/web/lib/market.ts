import type { KlineCacheResponse, SettingsPayload } from '../types/api';

export type MarketSelection = {
  source: string;
  symbol: string;
  timeframe: string;
};

function readNestedString(value: SettingsPayload | undefined, path: string[]): string {
  let cursor: unknown = value;
  for (const key of path) {
    if (!cursor || typeof cursor !== 'object' || !(key in cursor)) {
      return '';
    }
    cursor = (cursor as Record<string, unknown>)[key];
  }
  return typeof cursor === 'string' ? cursor : '';
}

export function marketSelectionFromResults(
  settings: SettingsPayload | undefined,
  cache: KlineCacheResponse | undefined,
): MarketSelection {
  if (cache) {
    return {
      source: cache.source,
      symbol: cache.symbol,
      timeframe: cache.timeframe,
    };
  }
  return {
    source: readNestedString(settings, ['general', 'last_data_source']),
    symbol: readNestedString(settings, ['general', 'last_symbol']),
    timeframe: readNestedString(settings, ['general', 'last_timeframe']),
  };
}
