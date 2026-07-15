import { describe, expect, it } from 'vitest';
import { marketSelectionFromResults } from '../lib/market';
import type { KlineCacheResponse, SettingsPayload } from '../types/api';

describe('marketSelectionFromResults', () => {
  it('uses the cache identity returned for the current backend selection', () => {
    const settings = {
      general: {
        last_data_source: 'eastmoney',
        last_symbol: '000001',
        last_timeframe: '1h',
      },
    } satisfies SettingsPayload;
    const cache: KlineCacheResponse = {
      available: false,
      source: 'tradingview',
      symbol: 'XAUUSD',
      timeframe: '15m',
    };

    expect(marketSelectionFromResults(settings, cache)).toEqual({
      source: 'tradingview',
      symbol: 'XAUUSD',
      timeframe: '15m',
    });
  });

  it('falls back to settings when no cache response is available', () => {
    const settings = {
      general: {
        last_data_source: 'akshare',
        last_symbol: '600519',
        last_timeframe: '1d',
      },
    } satisfies SettingsPayload;

    expect(marketSelectionFromResults(settings, undefined)).toEqual({
      source: 'akshare',
      symbol: '600519',
      timeframe: '1d',
    });
  });
});
