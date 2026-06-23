export type SettingsPayload = Record<string, unknown>;

export type DataSourceItem = {
  kind: string;
  label: string;
  default_symbol: string;
};

export type DataSourcesResponse = {
  items: DataSourceItem[];
};

export type TimeframesResponse = {
  items: string[];
};

export type KlineCacheResponse = {
  available: boolean;
  source: string;
  symbol: string;
  timeframe: string;
  saved_at?: string;
  bar_count?: number;
};

export type KlineBarPayload = {
  seq: number;
  ts_open: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number | null;
  pct_chg: number | null;
  closed: boolean;
};

export type KlineFramePayload = {
  symbol: string;
  timeframe: string;
  order: 'newest_first' | 'oldest_first';
  snapshot_ts_local_ms: number;
  bars: KlineBarPayload[];
  indicators: {
    ema20: Array<number | null>;
    atr14: Array<number | null>;
  };
};

export type MarketSnapshotResponse = {
  source: 'cache';
  cache_saved_at: string;
  frame: KlineFramePayload;
};

export type RecordSummary = {
  id: string;
  timestamp_local_iso: string;
  timestamp_local_ms: number;
  symbol: string;
  timeframe: string;
  bar_count: number;
  decision_stance: string;
  action: string;
  direction: string;
  has_exception: boolean;
};

export type RecordsResponse = {
  items: RecordSummary[];
};
