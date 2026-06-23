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
  bar_count: number;
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

export type AnalysisStatus = 'queued' | 'running' | 'cancelling' | 'succeeded' | 'failed' | 'cancelled';

export type AnalysisStartResponse = {
  analysis_id: string;
  status: AnalysisStatus;
  frame: KlineFramePayload;
  event_url: string;
};

export type AnalysisDecision = {
  decision?: Record<string, unknown>;
  order_type?: string;
  action?: string;
  direction?: string;
  order_direction?: string | null;
  entry?: number | string | null;
  entry_price?: number | string | null;
  take_profit?: number | string | null;
  take_profit_price?: number | string | null;
  stop_loss?: number | string | null;
  stop_loss_price?: number | string | null;
  estimated_win_rate?: number | string | null;
  confidence?: number | string | null;
  trade_confidence?: number | string | null;
  estimated_win_rate_basis?: string | null;
  historical_sample_count?: number | null;
  historical_win_rate_for_this_setup?: number | string | null;
  historical_expectancy_r?: number | string | null;
  reasoning?: string | null;
  [key: string]: unknown;
};

export type AnalysisRecordSummary = Partial<RecordSummary> & {
  record_id?: string;
  id?: string;
  symbol?: string;
  timeframe?: string;
};

export type AnalysisRecordPayload = AnalysisRecordSummary & {
  stage1_diagnosis?: Record<string, unknown> | null;
  stage2_decision?: AnalysisDecision | null;
  exception?: Record<string, unknown> | null;
  usage_total?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    cached_prompt_tokens?: number;
    [key: string]: unknown;
  };
};

export type AnalysisStatusResponse = {
  analysis_id: string;
  status: AnalysisStatus;
  event_count?: number;
  stage?: string;
  frame?: KlineFramePayload;
  record?: AnalysisRecordPayload | null;
  record_summary?: AnalysisRecordSummary;
  stage2_decision?: AnalysisDecision | null;
  usage_total?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    cache_hit_tokens?: number;
    [key: string]: unknown;
  };
  error?: string | null;
};

export type AnalysisCancelResponse = {
  analysis_id: string;
  status: AnalysisStatus;
};

export type AnalysisEvent =
  | { type: 'stage_started'; stage?: string; [key: string]: unknown }
  | { type: 'reasoning_delta'; stage?: string; text?: string; [key: string]: unknown }
  | { type: 'content_delta'; stage?: string; text?: string; [key: string]: unknown }
  | { type: 'record_saved'; record_id?: string; [key: string]: unknown }
  | { type: 'task_finished'; status?: AnalysisStatus; [key: string]: unknown }
  | { type: 'error'; stage?: string; message?: string; [key: string]: unknown }
  | { type: string; stage?: string; text?: string; message?: string; [key: string]: unknown };

export type BacktestRebuildResponse = {
  records_scanned: number;
  trade_signals: number;
  completed_trades: number;
  setup_buckets: number;
  output_path: string;
};

export type SetupStatsRow = {
  setup_key: string;
  key?: string;
  symbol_class?: string;
  timeframe_bucket?: string;
  cycle_position?: string;
  direction?: string;
  order_type?: string;
  patterns?: string;
  decision_stance?: string;
  sample_count: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  expectancy_r: number;
  total_r: number;
};

export type SetupStatsResponse = {
  rows: SetupStatsRow[];
};
