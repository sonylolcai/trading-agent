import { describe, expect, it } from 'vitest';
import { toChartCandles } from '../lib/chart';
import type { KlineFramePayload } from '../types/api';

describe('toChartCandles', () => {
  it('converts backend newest-first bars to chart oldest-first bars', () => {
    const frame: KlineFramePayload = {
      symbol: '000001',
      timeframe: '1h',
      bar_count: 2,
      order: 'newest_first',
      snapshot_ts_local_ms: 123,
      indicators: { ema20: [12, 10], atr14: [1.5, 1.2] },
      bars: [
        {
          seq: 1,
          ts_open: 3000,
          open: 10,
          high: 13,
          low: 9,
          close: 12,
          volume: 100,
          amount: 0,
          pct_chg: null,
          closed: true,
        },
        {
          seq: 2,
          ts_open: 2000,
          open: 9,
          high: 11,
          low: 8,
          close: 10,
          volume: 90,
          amount: 0,
          pct_chg: null,
          closed: true,
        },
      ],
    };

    expect(toChartCandles(frame).map((bar) => bar.seq)).toEqual([2, 1]);
    expect(toChartCandles(frame).map((bar) => bar.time)).toEqual([2, 3]);
  });
});
