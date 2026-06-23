import type { KlineFramePayload } from '../types/api';

export type ChartCandle = {
  time: number;
  seq: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
};

export function toChartCandles(frame: KlineFramePayload): ChartCandle[] {
  const bars = frame.order === 'newest_first' ? [...frame.bars].reverse() : [...frame.bars];
  return bars.map((bar) => ({
    time: Math.floor(bar.ts_open / 1000),
    seq: bar.seq,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
    closed: bar.closed,
  }));
}
