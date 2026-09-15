'use client';

import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Database,
  DownloadCloud,
  Layers,
  Play,
  RefreshCw,
  Save,
  Square,
  Terminal as TerminalIcon,
  Zap,
} from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { analysisEventsUrl, api, type ApiResult } from '../../lib/api';
import { marketSelectionFromResults, type MarketSelection } from '../../lib/market';
import type {
  AnalysisEvent,
  AnalysisRecordPayload,
  AnalysisStartResponse,
  AnalysisStatusResponse,
  DataSourcesResponse,
  KlineCacheResponse,
  MarketSnapshotResponse,
  RollingBacktestResponse,
  RiskProfile,
  SettingsPayload,
  TimeframesResponse,
} from '../../types/api';
import { parseAnalysisEvent, shouldFinalizeAnalysisStream } from '../analysis/analysis-event-stream';
import { appendAnalysisEventText, emptyStreamText, streamPaneDisplay, type StreamText } from '../analysis/analysis-stream-state';
import { AnalysisReportPanel } from '../analysis/analysis-report-panel';
import { KlineChartPreview } from '../chart/kline-chart-preview';
import { useI18n } from '../../lib/i18n/context';

type TerminalState = {
  settings: ApiResult<SettingsPayload> | null;
  sources: ApiResult<DataSourcesResponse> | null;
  cache: ApiResult<KlineCacheResponse> | null;
  snapshot: ApiResult<MarketSnapshotResponse> | null;
  rollingBacktest: ApiResult<RollingBacktestResponse> | null;
};

type AnalysisUiState = {
  start: ApiResult<AnalysisStartResponse> | null;
  status: ApiResult<AnalysisStatusResponse> | null;
  stream: StreamText;
  events: AnalysisEvent[];
  running: boolean;
  error: string;
  recordId: string;
};

const emptyState: TerminalState = {
  settings: null,
  sources: null,
  cache: null,
  snapshot: null,
  rollingBacktest: null,
};

const emptyMarketSelection: MarketSelection = {
  source: '',
  symbol: '',
  timeframe: '',
};

const riskProfileOptions: Array<{ value: RiskProfile; label: string; enLabel: string }> = [
  { value: 'conservative', label: '稳健', enLabel: 'Conservative' },
  { value: 'balanced', label: '均衡', enLabel: 'Balanced' },
  { value: 'aggressive', label: '进取', enLabel: 'Aggressive' },
  { value: 'extreme_aggressive', label: '强进取', enLabel: 'Extreme' },
];

const emptyStream: StreamText = emptyStreamText;

const emptyAnalysisState: AnalysisUiState = {
  start: null,
  status: null,
  stream: emptyStream,
  events: [],
  running: false,
  error: '',
  recordId: '',
};

function ErrorLine({ label, result }: { label: string; result: ApiResult<unknown> | null }) {
  if (!result || result.ok) {
    return null;
  }
  return (
    <div className="error-line">
      <AlertTriangle size={14} aria-hidden="true" />
      <span>{label}: {result.error}</span>
    </div>
  );
}

function marketPayload(selection: MarketSelection) {
  return {
    source: selection.source.trim(),
    symbol: selection.symbol.trim(),
    timeframe: selection.timeframe.trim(),
  };
}

function riskProfileFromSettings(settings: ApiResult<SettingsPayload> | null): RiskProfile {
  const raw = settings?.ok ? settings.data.general?.decision_stance : undefined;
  return riskProfileOptions.some((option) => option.value === raw) ? raw as RiskProfile : 'balanced';
}

function signalThresholdFromSettings(settings: ApiResult<SettingsPayload> | null): number | null {
  const raw = settings?.ok ? settings.data.general?.decision_confidence_threshold : undefined;
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

function analysisErrorFromStatus(status: ApiResult<AnalysisStatusResponse>, currentError: string): string {
  if (!status.ok) {
    return status.error;
  }
  if (status.data.status === 'succeeded' || status.data.status === 'cancelled') {
    return '';
  }
  return status.data.error ?? currentError;
}

function StreamPane({
  title,
  reasoning,
  content,
  bufferedContent,
  contentPending,
  contentComplete,
}: {
  title: string;
  reasoning: string;
  content: string;
  bufferedContent: string;
  contentPending: boolean;
  contentComplete: boolean;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const display = streamPaneDisplay({ reasoning, content, bufferedContent, contentPending, contentComplete });
  const isStreaming = !contentComplete && (Boolean(content) || Boolean(reasoning) || contentPending);

  const handleCopy = async () => {
    if (!display.body) return;
    try {
      await navigator.clipboard.writeText(display.body);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore clipboard error
    }
  };

  return (
    <div className="stream-pane-container">
      <div className="stream-pane-header">
        <div className="stream-pane-title-group">
          <div className="stream-pane-dots">
            <span className="dot dot--red" />
            <span className="dot dot--amber" />
            <span className="dot dot--green" />
          </div>
          <TerminalIcon size={13} className="text-muted" />
          <h3 className="stream-pane-title">{title}</h3>
        </div>
        <div className="stream-pane-actions">
          <StatusChip tone={display.tone} animated={isStreaming}>
            {contentPending ? 'buffering' : contentComplete ? 'ready' : isStreaming ? 'stream' : 'idle'}
          </StatusChip>
          {display.body && (
            <button
              className="stream-copy-btn"
              type="button"
              onClick={handleCopy}
              title={t.copy}
              aria-label="Copy stream output"
            >
              {copied ? <Check size={12} className="text-good" /> : <Copy size={12} />}
              <span>{copied ? t.copied : t.copy}</span>
            </button>
          )}
        </div>
      </div>
      <div className="stream-pane-body-wrap">
        <pre className="stream-pane-code">
          {display.body}
          {isStreaming && <span className="stream-cursor">▋</span>}
        </pre>
      </div>
    </div>
  );
}

function formatCompactNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(digits);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return `${value.toFixed(1)}%`;
}

function formatR(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}R`;
}

function translateDirection(value: string, locale: 'zh' | 'en' = 'zh'): string {
  const isLong = value === '做多' || value.toLowerCase() === 'long';
  const isShort = value === '做空' || value.toLowerCase() === 'short';
  if (isLong) {
    return locale === 'en' ? 'Long' : '做多';
  }
  if (isShort) {
    return locale === 'en' ? 'Short' : '做空';
  }
  return value || 'n/a';
}

function translateStatus(value: string, locale: 'zh' | 'en' = 'zh'): string {
  if (locale === 'en') {
    const mapEn: Record<string, string> = {
      win: 'Take Profit',
      loss: 'Stop Loss',
      open: 'In Position',
      not_triggered: 'Not Triggered',
      invalid: 'Invalid',
      skipped: 'Skipped',
    };
    return mapEn[value] ?? value;
  }
  const map: Record<string, string> = {
    win: '止盈',
    loss: '止损',
    open: '持仓中',
    not_triggered: '未触发',
    invalid: '无效',
    skipped: '跳过',
  };
  return map[value] ?? value;
}

function RollingMetricCard({
  label,
  value,
  tone = 'neutral',
  subtitle,
}: {
  label: string;
  value: string | number;
  tone?: 'good' | 'warn' | 'bad' | 'info' | 'neutral';
  subtitle?: string;
}) {
  return (
    <div className={`rolling-backtest__metric rolling-backtest__metric--${tone}`}>
      <div className="metric-card-top">
        <span className="metric-label">{label}</span>
      </div>
      <strong className="metric-value">{value}</strong>
      {subtitle && <span className="metric-sub">{subtitle}</span>}
    </div>
  );
}

function RollingBacktestDashboard({ result }: { result: ApiResult<RollingBacktestResponse> | null }) {
  const { t, locale } = useI18n();
  const data = result?.ok ? result.data : null;
  const tradeRows = data?.trades ?? [];
  const hasSignals = Boolean(data && data.trade_signals > 0);
  const statusTone = !result ? 'neutral' : result.ok ? 'good' : 'warn';
  const profile = data?.risk_profile ?? 'n/a';

  return (
    <section className="rolling-backtest" aria-label={t.rollingBacktestTitle}>
      <div className="rolling-backtest__head">
        <div>
          <h3>{t.rollingBacktestTitle}</h3>
          <p>
            {data
              ? `${data.symbol} ${data.timeframe} / ${data.bar_count} bars / ${data.evaluated_windows} windows / ${profile}`
              : t.rollingBacktestWarming}
          </p>
        </div>
        <StatusChip tone={statusTone}>{data ? 'dashboard' : result ? 'offline' : 'loading'}</StatusChip>
      </div>

      {result && !result.ok ? (
        <div className="error-block">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{t.rollingBacktestWarming}: {result.error}</span>
        </div>
      ) : null}

      <div className="rolling-backtest__metrics">
        <RollingMetricCard label={t.evaluatedWindows} value={data?.evaluated_windows ?? 0} tone="info" subtitle="Windows" />
        <RollingMetricCard label={t.tradeSignals} value={data?.trade_signals ?? 0} tone={hasSignals ? 'good' : 'neutral'} subtitle="Signals" />
        <RollingMetricCard label={t.completedTrades} value={data?.completed_trades ?? 0} tone={data?.completed_trades ? 'good' : 'neutral'} subtitle="Trades" />
        <RollingMetricCard label={t.winRate} value={formatPercent(data?.win_rate_pct)} tone={(data?.win_rate_pct ?? 0) >= 50 ? 'good' : 'warn'} subtitle="Win Rate" />
        <RollingMetricCard label={t.expectancyR} value={formatR(data?.expectancy_r)} tone={(data?.expectancy_r ?? 0) > 0 ? 'good' : 'warn'} subtitle="Expectancy" />
        <RollingMetricCard label={t.totalR} value={formatR(data?.total_r)} tone={(data?.total_r ?? 0) > 0 ? 'good' : 'warn'} subtitle="Cumulative R" />
        <RollingMetricCard label={t.maxDrawdown} value={formatR(data?.max_drawdown_r ? -Math.abs(data.max_drawdown_r) : 0)} tone={(data?.max_drawdown_r ?? 0) > 0 ? 'warn' : 'neutral'} subtitle="Max DD" />
        <RollingMetricCard label={t.profitFactor} value={formatCompactNumber(data?.profit_factor)} tone={(data?.profit_factor ?? 0) >= 1 ? 'good' : 'neutral'} subtitle="PF Ratio" />
      </div>

      {data && !hasSignals ? (
        <div className="rolling-backtest__empty">
          {t.rollingEmpty}
        </div>
      ) : null}

      {tradeRows.length > 0 ? (
        <div className="rolling-backtest__table-wrap">
          <table className="rolling-backtest__table">
            <thead>
              <tr>
                <th>{t.thDirection}</th>
                <th>{t.thOrder}</th>
                <th>{t.thEntry}</th>
                <th>{t.thStopLoss}</th>
                <th>{t.thTakeProfit}</th>
                <th>{t.thStatus}</th>
                <th>{t.thRPnL}</th>
                <th>{t.thBarsHeld}</th>
              </tr>
            </thead>
            <tbody>
              {tradeRows.slice(0, 12).map((trade) => {
                const isLong = trade.direction === '做多' || trade.direction.toLowerCase() === 'long';
                const isWin = trade.status === 'win';
                const isLoss = trade.status === 'loss';
                const rVal = trade.r_multiple ?? 0;
                return (
                  <tr key={`${trade.signal_index}-${trade.entry_index ?? 'pending'}-${trade.exit_index ?? 'open'}`}>
                    <td>
                      <span className={`direction-badge ${isLong ? 'direction-badge--long' : 'direction-badge--short'}`}>
                        {isLong ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                        <span>{translateDirection(trade.direction, locale)}</span>
                      </span>
                    </td>
                    <td><span className="order-type-chip">{trade.order_type}</span></td>
                    <td className="tabular-num">{formatCompactNumber(trade.entry_price, 3)}</td>
                    <td className="tabular-num text-bad">{formatCompactNumber(trade.stop_loss_price, 3)}</td>
                    <td className="tabular-num text-good">{formatCompactNumber(trade.take_profit_price, 3)}</td>
                    <td>
                      <span className={`trade-status-chip ${isWin ? 'trade-status-chip--win' : isLoss ? 'trade-status-chip--loss' : 'trade-status-chip--open'}`}>
                        {translateStatus(trade.status, locale)}
                      </span>
                    </td>
                    <td>
                      <span className={`r-multiple-pill ${rVal > 0 ? 'r-multiple-pill--pos' : rVal < 0 ? 'r-multiple-pill--neg' : ''}`}>
                        {formatR(trade.r_multiple)}
                      </span>
                    </td>
                    <td className="tabular-num">{trade.bars_held}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

export function TerminalWorkbench() {
  const { t, locale } = useI18n();
  const [state, setState] = useState<TerminalState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [timeframes, setTimeframes] = useState<ApiResult<TimeframesResponse> | null>(null);
  const [marketForm, setMarketForm] = useState<MarketSelection>(emptyMarketSelection);
  const [marketBusy, setMarketBusy] = useState(false);
  const [marketMessage, setMarketMessage] = useState('');
  const [marketError, setMarketError] = useState('');
  const [riskProfileBusy, setRiskProfileBusy] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisUiState>(emptyAnalysisState);
  const [streamExpanded, setStreamExpanded] = useState(true);

  async function load() {
    setLoading(true);
    const [settings, sources, cache, snapshot, rollingBacktest] = await Promise.all([
      api.settings(),
      api.dataSources(),
      api.klineCache(),
      api.snapshot(),
      api.rollingBacktestSummary({ window: 100 }),
    ]);
    setState({ settings, sources, cache, snapshot, rollingBacktest });
    setMarketForm(
      marketSelectionFromResults(
        settings.ok ? settings.data : undefined,
        cache.ok ? cache.data : undefined,
      ),
    );
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!marketForm.source) {
      setTimeframes(null);
      return;
    }
    let cancelled = false;
    void api.timeframes(marketForm.source).then((result) => {
      if (cancelled) {
        return;
      }
      setTimeframes(result);
      if (result.ok && result.data.items.length > 0) {
        setMarketForm((current) => {
          if (current.source !== marketForm.source || result.data.items.includes(current.timeframe)) {
            return current;
          }
          return { ...current, timeframe: result.data.items[0] };
        });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [marketForm.source]);

  useEffect(() => {
    const id = analysis.start?.ok ? analysis.start.data.analysis_id : '';
    if (!id || !analysis.running) {
      return undefined;
    }

    const events = new EventSource(analysisEventsUrl(id));
    events.addEventListener('message', (message) => {
      const event = parseAnalysisEvent(`data: ${message.data}\n\n`);
      if (!event) {
        return;
      }
      setAnalysis((current) => ({
        ...current,
        stream: appendAnalysisEventText(current.stream, event),
        events: [...current.events, event],
        error: event.type === 'error' ? event.message ?? 'Analysis stream failed' : current.error,
        recordId: event.type === 'record_saved' && typeof event.record_id === 'string' ? event.record_id : current.recordId,
      }));
      if (shouldFinalizeAnalysisStream(event)) {
        events.close();
        setAnalysis((current) => ({ ...current, running: false }));
        void api.analysisStatus(id).then((status) => setAnalysis((current) => ({ ...current, status, error: analysisErrorFromStatus(status, current.error) })));
      }
    });
    events.onerror = () => {
      events.close();
      setAnalysis((current) => ({ ...current, running: false, error: current.error || 'Analysis event stream disconnected' }));
      void api.analysisStatus(id).then((status) => setAnalysis((current) => ({ ...current, status, error: analysisErrorFromStatus(status, current.error) })));
    };

    return () => events.close();
  }, [analysis.running, analysis.start]);

  async function startAnalysis() {
    setMarketMessage('Checking K-line data');
    setMarketError('');
    setAnalysis({ ...emptyAnalysisState, running: true });
    const saved = await api.updateMarketSelection(marketPayload(marketForm));
    if (!saved.ok) {
      setMarketError(saved.error);
      setMarketMessage('');
      setAnalysis({ ...emptyAnalysisState, start: null, running: false, error: saved.error });
      return;
    }
    const start = await api.startAnalysis();
    if (!start.ok) {
      setAnalysis({ ...emptyAnalysisState, start, running: false, error: start.error });
      setMarketError(start.error);
      setMarketMessage('');
      return;
    }
    setMarketMessage('Analysis started');
    setAnalysis((current) => ({ ...current, start, running: true }));
    void load();
  }

  async function saveMarketSelection() {
    setMarketBusy(true);
    setMarketError('');
    setMarketMessage('Saving selection');
    const saved = await api.updateMarketSelection(marketPayload(marketForm));
    if (!saved.ok) {
      setMarketError(saved.error);
      setMarketMessage('');
      setMarketBusy(false);
      return;
    }
    setMarketMessage('Selection saved');
    await load();
    setMarketBusy(false);
  }

  async function fetchMarketData() {
    setMarketBusy(true);
    setMarketError('');
    setMarketMessage('Fetching K-line data');
    const fetched = await api.fetchKlines(marketPayload(marketForm));
    if (!fetched.ok) {
      setMarketError(fetched.error);
      setMarketMessage('');
      setMarketBusy(false);
      return;
    }
    setMarketMessage(`Fetched ${fetched.data.bar_count ?? 0} bars`);
    await load();
    setMarketBusy(false);
  }

  async function updateRiskProfile(riskProfile: RiskProfile) {
    setRiskProfileBusy(true);
    setMarketError('');
    const saved = await api.updateRiskProfile({ risk_profile: riskProfile });
    if (!saved.ok) {
      setMarketError(saved.error);
      setRiskProfileBusy(false);
      return;
    }
    const opt = riskProfileOptions.find((option) => option.value === riskProfile);
    const label = locale === 'en' ? (opt?.enLabel ?? riskProfile) : (opt?.label ?? riskProfile);
    setMarketMessage(locale === 'zh' ? `风险档位已切换为 ${label}` : `Risk profile updated to ${label}`);
    await load();
    setRiskProfileBusy(false);
  }

  async function cancelAnalysis() {
    const id = analysis.start?.ok ? analysis.start.data.analysis_id : '';
    if (!id) {
      return;
    }
    const cancelled = await api.cancelAnalysis(id);
    setAnalysis((current) => ({
      ...current,
      status: cancelled,
      running: cancelled.ok,
      error: cancelled.ok ? 'Cancellation requested.' : cancelled.error,
    }));
  }

  const sourceItems = state.sources?.ok ? state.sources.data.items : [];
  const timeframeItems = timeframes?.ok ? timeframes.data.items : [];
  const controlsDisabled = loading || marketBusy || analysis.running;
  const riskProfileDisabled = loading || riskProfileBusy || analysis.running;
  const activeRiskProfile = riskProfileFromSettings(state.settings);
  const activeSignalThreshold = signalThresholdFromSettings(state.settings);
  const snapshotFrame = state.snapshot?.ok ? state.snapshot.data.frame : undefined;
  const analysisStatus = analysis.status?.ok ? analysis.status.data : undefined;
  const decision = analysisStatus?.stage2_decision ?? analysisStatus?.record?.stage2_decision ?? undefined;
  const reportRecord: AnalysisRecordPayload | undefined = analysisStatus?.record ?? (decision ? { stage2_decision: decision } : undefined);
  const analysisReport = analysisStatus?.analysis_report ?? analysisStatus?.record?.analysis_report ?? undefined;
  const analysisFrame = analysis.start?.ok ? analysis.start.data.frame : analysisStatus?.frame;
  const recordLabel = analysis.recordId
    ? `record ${analysis.recordId}`
    : analysisStatus?.record_summary?.symbol && analysisStatus.record_summary.timeframe
      ? `${analysisStatus.record_summary.symbol} ${analysisStatus.record_summary.timeframe}`
      : 'Stage 2 output';
  const analysisTone = analysis.running ? 'info' : analysis.error || analysis.status?.ok === false ? 'bad' : analysisStatus?.status === 'succeeded' ? 'good' : 'neutral';
  return (
    <AppShell title={t.navTerminal}>
      <section className="terminal-grid">
        {/* Quick Symbol Presets Bar */}
        <div className="terminal-presets-bar">
          <div className="terminal-presets-label">
            <Zap size={13} className="text-accent" />
            <span>{t.quickPresets}:</span>
          </div>
          <div className="terminal-presets-list">
            {[
              { label: 'BTC/USDT', source: 'crypto', symbol: 'BTCUSDT', tf: '1d' },
              { label: 'ETH/USDT', source: 'crypto', symbol: 'ETHUSDT', tf: '1d' },
              { label: 'SOL/USDT', source: 'crypto', symbol: 'SOLUSDT', tf: '1d' },
              { label: '000001 平安银行', source: 'eastmoney', symbol: '000001', tf: '1d' },
              { label: '600519 贵州茅台', source: 'eastmoney', symbol: '600519', tf: '1d' },
            ].map((preset) => (
              <button
                key={preset.symbol}
                type="button"
                className={`terminal-preset-chip ${marketForm.symbol === preset.symbol ? 'terminal-preset-chip--active' : ''}`}
                disabled={controlsDisabled}
                onClick={() => {
                  setMarketForm({
                    source: preset.source,
                    symbol: preset.symbol,
                    timeframe: preset.tf,
                  });
                }}
              >
                <span>{preset.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="control-strip">
          <div className="market-form">
            <label className="market-field">
              <span>{t.source}</span>
              <select
                value={marketForm.source}
                onChange={(event) => {
                  const item = sourceItems.find((source) => source.kind === event.target.value);
                  setMarketForm((current) => ({
                    ...current,
                    source: event.target.value,
                    symbol: item?.default_symbol ?? current.symbol,
                  }));
                }}
                disabled={controlsDisabled}
              >
                <option value="" disabled>{t.source}</option>
                {sourceItems.map((source) => (
                  <option key={source.kind} value={source.kind}>{source.label}</option>
                ))}
              </select>
            </label>
            <label className="market-field market-field--symbol">
              <span>{t.symbol}</span>
              <input
                value={marketForm.symbol}
                onChange={(event) => setMarketForm((current) => ({ ...current, symbol: event.target.value }))}
                disabled={controlsDisabled}
                placeholder="000001"
              />
            </label>
            <label className="market-field">
              <span>{t.timeframe}</span>
              <select
                value={marketForm.timeframe}
                onChange={(event) => setMarketForm((current) => ({ ...current, timeframe: event.target.value }))}
                disabled={controlsDisabled || timeframeItems.length === 0}
              >
                {marketForm.timeframe && !timeframeItems.includes(marketForm.timeframe) ? (
                  <option value={marketForm.timeframe}>{marketForm.timeframe}</option>
                ) : null}
                {timeframeItems.map((timeframe) => (
                  <option key={timeframe} value={timeframe}>{timeframe}</option>
                ))}
              </select>
            </label>
            <div className="market-field market-field--risk">
              <label htmlFor="risk-profile-select">
                <span>{t.riskProfile}</span>
              </label>
              <select
                id="risk-profile-select"
                value={activeRiskProfile}
                onChange={(event) => void updateRiskProfile(event.target.value as RiskProfile)}
                disabled={riskProfileDisabled}
              >
                {riskProfileOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {locale === 'en' ? option.enLabel : option.label}
                  </option>
                ))}
              </select>
              <div className="risk-profile-segmented">
                {riskProfileOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={`risk-pill ${activeRiskProfile === option.value ? 'risk-pill--active' : ''} risk-pill--${option.value}`}
                    disabled={riskProfileDisabled}
                    onClick={() => void updateRiskProfile(option.value)}
                  >
                    {locale === 'en' ? option.enLabel : option.label}
                  </button>
                ))}
              </div>
            </div>
            <label className="market-field">
              <span>{t.signalThreshold}</span>
              <input
                value={activeSignalThreshold === null ? 'n/a' : String(activeSignalThreshold)}
                disabled
                readOnly
              />
            </label>
          </div>
          <div className="control-actions">
            <button className="icon-button" type="button" onClick={() => void saveMarketSelection()} disabled={controlsDisabled} aria-label="Apply market selection">
              <Save size={15} aria-hidden="true" />
              <span>{t.apply}</span>
            </button>
            <button className="icon-button" type="button" onClick={() => void fetchMarketData()} disabled={controlsDisabled} aria-label="Fetch K-line data">
              <DownloadCloud size={15} aria-hidden="true" />
              <span>{t.fetchData}</span>
            </button>
            <button className="icon-button" type="button" onClick={() => void load()} disabled={loading || marketBusy} aria-label="Refresh snapshot">
              <RefreshCw size={15} aria-hidden="true" />
              <span>{loading ? t.loading : t.refresh}</span>
            </button>
            <button className="icon-button" type="button" onClick={() => void startAnalysis()} disabled={analysis.running || loading || marketBusy} aria-label="Submit analysis">
              <Play size={15} aria-hidden="true" />
              <span>{t.analyze}</span>
            </button>
            {analysis.running ? (
              <button className="icon-button" type="button" onClick={() => void cancelAnalysis()} aria-label="Cancel analysis">
                <Square size={14} aria-hidden="true" />
                <span>{t.cancel}</span>
              </button>
            ) : null}
          </div>
          {marketError ? (
            <div className="market-status market-status--bad">
              <AlertTriangle size={14} aria-hidden="true" />
              <span>{marketError}</span>
            </div>
          ) : marketMessage ? (
            <div className="market-status">
              <Database size={14} aria-hidden="true" />
              <span>{marketMessage}</span>
            </div>
          ) : null}
        </div>

        <section className="panel" style={{ gridColumn: '1 / -1' }}>
          <div className="panel__header">
            <div>
              <h2>{t.analysisStream}</h2>
              <p>{analysisFrame ? `${analysisFrame.symbol} ${analysisFrame.timeframe} / ${analysisFrame.bar_count} bars` : 'Submit cached closed-bar frame'}</p>
            </div>
            <div className="panel__actions">
              <StatusChip tone={analysisTone} animated={analysis.running}>{analysis.running ? 'running' : analysisStatus?.status ?? 'idle'}</StatusChip>
              <button
                className="collapse-button"
                type="button"
                aria-expanded={streamExpanded}
                onClick={() => setStreamExpanded((current) => !current)}
              >
                {streamExpanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                <span>{streamExpanded ? t.collapse : t.expand}</span>
              </button>
            </div>
          </div>
          {streamExpanded ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10, marginTop: 10 }}>
                <StreamPane
                  title="Stage 1"
                  reasoning={analysis.stream.stage1Reasoning}
                  content={analysis.stream.stage1Content}
                  bufferedContent={analysis.stream.stage1BufferedContent}
                  contentPending={analysis.stream.stage1ContentPending}
                  contentComplete={analysis.stream.stage1ContentComplete}
                />
                <StreamPane
                  title="Stage 2"
                  reasoning={analysis.stream.stage2Reasoning}
                  content={analysis.stream.stage2Content}
                  bufferedContent={analysis.stream.stage2BufferedContent}
                  contentPending={analysis.stream.stage2ContentPending}
                  contentComplete={analysis.stream.stage2ContentComplete}
                />
              </div>
              {analysis.error ? (
                <div className="error-block">
                  <AlertTriangle size={16} aria-hidden="true" />
                  <span>{analysis.error}</span>
                </div>
              ) : null}
              <ErrorLine label="Analysis start" result={analysis.start} />
              <ErrorLine label="Analysis status" result={analysis.status} />
            </>
          ) : null}
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <h2>{t.analysisReport}</h2>
              <p>{recordLabel}</p>
            </div>
            <StatusChip tone={analysisReport || decision ? 'good' : 'neutral'}>{analysisReport ? 'report' : decision ? 'fallback' : 'pending'}</StatusChip>
          </div>
          <AnalysisReportPanel record={reportRecord} report={analysisReport} />
          <RollingBacktestDashboard result={state.rollingBacktest} />
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <h2>{t.klineSnapshot}</h2>
              <p>{snapshotFrame ? `${snapshotFrame.symbol} ${snapshotFrame.timeframe}` : 'Read-only cache preview'}</p>
            </div>
            <StatusChip tone={state.snapshot?.ok ? 'good' : 'bad'}>{state.snapshot?.ok ? 'cache' : 'offline'}</StatusChip>
          </div>
          <KlineChartPreview frame={snapshotFrame} />
          <ErrorLine label="Snapshot" result={state.snapshot} />
        </section>

      </section>
    </AppShell>
  );
}
