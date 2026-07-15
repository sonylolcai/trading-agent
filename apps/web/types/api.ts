export type RiskProfile = 'conservative' | 'balanced' | 'aggressive' | 'extreme_aggressive';

export type SettingsPayload = {
  provider?: Record<string, unknown>;
  general?: {
    last_data_source?: string;
    last_symbol?: string;
    last_timeframe?: string;
    decision_stance?: RiskProfile | string;
    decision_confidence_threshold?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type RiskProfileRequest = {
  risk_profile: RiskProfile;
};

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

export type MarketSelectionRequest = {
  source?: string;
  symbol?: string;
  timeframe?: string;
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
  decision_confidence_threshold?: number | null;
  action: string;
  direction: string;
  has_exception: boolean;
  stage1_diagnosis?: Record<string, unknown> | null;
  stage2_decision?: AnalysisDecision | null;
  analysis_report?: AnalysisReport | null;
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

export type AnalysisReportTone = 'good' | 'warn' | 'bad' | 'info' | 'neutral';

export type AnalysisReport = {
  headline: {
    action?: string | null;
    direction?: string | null;
    summary?: string;
    risk?: string;
  };
  metrics: Array<{
    label: string;
    value: string | number | null;
    unit?: string;
    tone?: AnalysisReportTone;
  }>;
  decision: {
    order_type?: string | null;
    direction?: string | null;
    risk_profile?: string | null;
    signal_threshold?: number | string | null;
    entry_price?: number | null;
    stop_loss_price?: number | null;
    take_profit_price?: number | null;
    terminal?: Record<string, unknown> | null;
  };
  evidence_tables: Array<{
    title: string;
    rows: Array<{
      node_id?: string;
      section?: string;
      question?: string;
      answer?: string;
      reason?: string;
      bar_range?: string;
      skipped?: boolean;
    }>;
  }>;
  flows: Array<{
    title: string;
    items: Array<{
      id: string;
      label?: string;
      value?: string;
      detail?: string;
      tone?: string;
    }>;
  }>;
  probability_blocks: Array<{
    title: string;
    items: Array<{ label: string; value: number }>;
    reasoning?: string;
  }>;
  lists: Array<{ title: string; items: string[] }>;
};

export type AnalysisRecordSummary = Partial<RecordSummary> & {
  record_id?: string;
  id?: string;
  symbol?: string;
  timeframe?: string;
};

export type AnalysisRecordPayload = AnalysisRecordSummary & {
  analysis_report?: AnalysisReport | null;
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
  analysis_report?: AnalysisReport | null;
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
  | { type: 'content_started'; stage?: string; format?: string; [key: string]: unknown }
  | { type: 'content_delta'; stage?: string; text?: string; [key: string]: unknown }
  | { type: 'content_finished'; stage?: string; format?: string; text?: string; [key: string]: unknown }
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

export type RollingBacktestTrade = {
  signal_index: number;
  signal_seq: number;
  entry_index: number | null;
  entry_seq: number | null;
  exit_index: number | null;
  exit_seq: number | null;
  order_type: string;
  direction: string;
  entry_price: number;
  stop_loss_price: number;
  take_profit_price: number;
  status: string;
  r_multiple: number;
  bars_held: number;
  reason: string;
};

export type RollingBacktestResponse = {
  source: string;
  symbol: string;
  timeframe: string;
  window: number;
  bar_count: number;
  evaluated_windows: number;
  trade_signals: number;
  completed_trades: number;
  wins: number;
  losses: number;
  open_trades: number;
  not_triggered: number;
  invalid: number;
  win_rate_pct: number;
  expectancy_r: number;
  average_r: number;
  total_r: number;
  profit_factor: number | null;
  max_drawdown_r: number;
  skipped_no_setup: number;
  skipped_no_followthrough: number;
  risk_profile?: string;
  trades: RollingBacktestTrade[];
};
