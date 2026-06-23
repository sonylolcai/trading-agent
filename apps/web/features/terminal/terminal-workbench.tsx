'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Database, KeyRound, Play, RefreshCw, Square } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { analysisEventsUrl, api, type ApiResult } from '../../lib/api';
import type {
  AnalysisEvent,
  AnalysisStartResponse,
  AnalysisStatusResponse,
  DataSourcesResponse,
  KlineCacheResponse,
  MarketSnapshotResponse,
  SettingsPayload,
} from '../../types/api';
import { parseAnalysisEvent, shouldFinalizeAnalysisStream } from '../analysis/analysis-event-stream';
import { DecisionStatsBasis, DecisionSummary } from '../analysis/decision-summary';
import { KlineChartPreview } from '../chart/kline-chart-preview';

type TerminalState = {
  settings: ApiResult<SettingsPayload> | null;
  sources: ApiResult<DataSourcesResponse> | null;
  cache: ApiResult<KlineCacheResponse> | null;
  snapshot: ApiResult<MarketSnapshotResponse> | null;
};

type StreamText = {
  stage1Reasoning: string;
  stage1Content: string;
  stage2Reasoning: string;
  stage2Content: string;
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
};

const emptyStream: StreamText = {
  stage1Reasoning: '',
  stage1Content: '',
  stage2Reasoning: '',
  stage2Content: '',
};

const emptyAnalysisState: AnalysisUiState = {
  start: null,
  status: null,
  stream: emptyStream,
  events: [],
  running: false,
  error: '',
  recordId: '',
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

function analysisErrorFromStatus(status: ApiResult<AnalysisStatusResponse>, currentError: string): string {
  if (!status.ok) {
    return status.error;
  }
  if (status.data.status === 'succeeded' || status.data.status === 'cancelled') {
    return '';
  }
  return status.data.error ?? currentError;
}

function appendEventText(stream: StreamText, event: AnalysisEvent): StreamText {
  if (event.type !== 'reasoning_delta' && event.type !== 'content_delta') {
    return stream;
  }
  const text = event.text ?? '';
  if (!text) {
    return stream;
  }
  if (event.stage === 'stage1' && event.type === 'reasoning_delta') {
    return { ...stream, stage1Reasoning: stream.stage1Reasoning + text };
  }
  if (event.stage === 'stage1') {
    return { ...stream, stage1Content: stream.stage1Content + text };
  }
  if (event.stage === 'stage2' && event.type === 'reasoning_delta') {
    return { ...stream, stage2Reasoning: stream.stage2Reasoning + text };
  }
  if (event.stage === 'stage2') {
    return { ...stream, stage2Content: stream.stage2Content + text };
  }
  return stream;
}

function StreamPane({ title, reasoning, content }: { title: string; reasoning: string; content: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div className="panel__header">
        <h3 style={{ margin: 0, fontSize: 13 }}>{title}</h3>
        <StatusChip tone={content || reasoning ? 'good' : 'neutral'}>{content || reasoning ? 'stream' : 'idle'}</StatusChip>
      </div>
      <pre style={{ minHeight: 128, margin: '8px 0 0', overflow: 'auto', whiteSpace: 'pre-wrap', color: 'var(--muted)', fontFamily: 'var(--mono)', fontSize: 12 }}>
        {reasoning ? `[reasoning]\n${reasoning}\n\n` : ''}
        {content ? `[content]\n${content}` : 'Waiting for stream output.'}
      </pre>
    </div>
  );
}

export function TerminalWorkbench() {
  const [state, setState] = useState<TerminalState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState<AnalysisUiState>(emptyAnalysisState);

  async function load() {
    setLoading(true);
    const [settings, sources, cache, snapshot] = await Promise.all([
      api.settings(),
      api.dataSources(),
      api.klineCache(),
      api.snapshot(),
    ]);
    setState({ settings, sources, cache, snapshot });
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

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
        stream: appendEventText(current.stream, event),
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
    setAnalysis({ ...emptyAnalysisState, running: true });
    const start = await api.startAnalysis();
    if (!start.ok) {
      setAnalysis({ ...emptyAnalysisState, start, running: false, error: start.error });
      return;
    }
    setAnalysis((current) => ({ ...current, start, running: true }));
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

  const settingsData = state.settings?.ok ? state.settings.data : undefined;
  const providerKey = readNestedString(settingsData, ['provider', 'api_key']);
  const currentSource = state.cache?.ok ? state.cache.data.source : readNestedString(settingsData, ['general', 'last_data_source']);
  const currentSymbol = state.cache?.ok ? state.cache.data.symbol : readNestedString(settingsData, ['general', 'last_symbol']);
  const currentTimeframe = state.cache?.ok ? state.cache.data.timeframe : readNestedString(settingsData, ['general', 'last_timeframe']);
  const snapshotFrame = state.snapshot?.ok ? state.snapshot.data.frame : undefined;
  const analysisStatus = analysis.status?.ok ? analysis.status.data : undefined;
  const decision = analysisStatus?.stage2_decision ?? analysisStatus?.record?.stage2_decision ?? undefined;
  const analysisFrame = analysis.start?.ok ? analysis.start.data.frame : analysisStatus?.frame;
  const recordLabel = analysis.recordId
    ? `record ${analysis.recordId}`
    : analysisStatus?.record_summary?.symbol && analysisStatus.record_summary.timeframe
      ? `${analysisStatus.record_summary.symbol} ${analysisStatus.record_summary.timeframe}`
      : 'Stage 2 output';
  const analysisTone = analysis.running ? 'info' : analysis.error || analysis.status?.ok === false ? 'bad' : analysisStatus?.status === 'succeeded' ? 'good' : 'neutral';
  const firstSourceLabel = useMemo(() => {
    if (!state.sources?.ok) {
      return 'sources offline';
    }
    return state.sources.data.items.map((item) => item.label).join(' / ');
  }, [state.sources]);

  return (
    <AppShell title="Terminal">
      <section className="terminal-grid">
        <div className="control-strip">
          <div className="control-field">
            <span>Source</span>
            <strong>{currentSource || 'unknown'}</strong>
          </div>
          <div className="control-field">
            <span>Symbol</span>
            <strong>{currentSymbol || 'unset'}</strong>
          </div>
          <div className="control-field">
            <span>Timeframe</span>
            <strong>{currentTimeframe || 'unset'}</strong>
          </div>
          <button className="icon-button" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh snapshot">
            <RefreshCw size={15} aria-hidden="true" />
            <span>{loading ? 'Loading' : 'Refresh'}</span>
          </button>
          <button className="icon-button" type="button" onClick={() => void startAnalysis()} disabled={analysis.running || loading} aria-label="Submit analysis">
            <Play size={15} aria-hidden="true" />
            <span>Analyze</span>
          </button>
          {analysis.running ? (
            <button className="icon-button" type="button" onClick={() => void cancelAnalysis()} aria-label="Cancel analysis">
              <Square size={14} aria-hidden="true" />
              <span>Cancel</span>
            </button>
          ) : null}
        </div>

        <section className="panel" style={{ gridColumn: '1 / -1' }}>
          <div className="panel__header">
            <div>
              <h2>Analysis Stream</h2>
              <p>{analysisFrame ? `${analysisFrame.symbol} ${analysisFrame.timeframe} / ${analysisFrame.bar_count} bars` : 'Submit cached closed-bar frame'}</p>
            </div>
            <StatusChip tone={analysisTone}>{analysis.running ? 'running' : analysisStatus?.status ?? 'idle'}</StatusChip>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10, marginTop: 10 }}>
            <StreamPane title="Stage 1" reasoning={analysis.stream.stage1Reasoning} content={analysis.stream.stage1Content} />
            <StreamPane title="Stage 2" reasoning={analysis.stream.stage2Reasoning} content={analysis.stream.stage2Content} />
          </div>
          {analysis.error ? (
            <div className="error-block">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{analysis.error}</span>
            </div>
          ) : null}
          <ErrorLine label="Analysis start" result={analysis.start} />
          <ErrorLine label="Analysis status" result={analysis.status} />
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <h2>Decision</h2>
              <p>{recordLabel}</p>
            </div>
            <StatusChip tone={decision ? 'good' : 'neutral'}>{decision ? 'ready' : 'pending'}</StatusChip>
          </div>
          <DecisionSummary decision={decision} />
          <div style={{ marginTop: 12 }}>
            <div className="panel__header">
              <h3 style={{ margin: 0, fontSize: 13 }}>Stats Basis</h3>
              <StatusChip tone={decision?.historical_sample_count ? 'info' : 'neutral'}>setup</StatusChip>
            </div>
            <DecisionStatsBasis decision={decision} />
          </div>
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <h2>K-line Snapshot</h2>
              <p>{snapshotFrame ? `${snapshotFrame.symbol} ${snapshotFrame.timeframe}` : 'Read-only cache preview'}</p>
            </div>
            <StatusChip tone={state.snapshot?.ok ? 'good' : 'bad'}>{state.snapshot?.ok ? 'cache' : 'offline'}</StatusChip>
          </div>
          <KlineChartPreview frame={snapshotFrame} />
          <ErrorLine label="Snapshot" result={state.snapshot} />
        </section>

        <section className="panel">
          <div className="panel__header">
            <div>
              <h2>Runtime</h2>
              <p>{firstSourceLabel}</p>
            </div>
            <StatusChip tone={providerKey ? 'info' : 'warn'}>{providerKey ? 'masked key' : 'key missing'}</StatusChip>
          </div>
          <div className="metrics-grid">
            <div>
              <span>Cache</span>
              <strong>{state.cache?.ok && state.cache.data.available ? 'available' : 'missing'}</strong>
            </div>
            <div>
              <span>Bars</span>
              <strong>{state.cache?.ok && state.cache.data.bar_count ? state.cache.data.bar_count : '0'}</strong>
            </div>
            <div>
              <span>Saved</span>
              <strong>{state.cache?.ok && state.cache.data.saved_at ? state.cache.data.saved_at : 'n/a'}</strong>
            </div>
            <div>
              <span>Snapshot bars</span>
              <strong>{snapshotFrame?.bars.length ?? 0}</strong>
            </div>
          </div>
          <div className="side-list">
            <div><Database size={14} aria-hidden="true" /> GET /api/market/snapshot</div>
            <div><KeyRound size={14} aria-hidden="true" /> GET /api/settings</div>
            <div><Play size={14} aria-hidden="true" /> POST /api/analysis</div>
          </div>
          <ErrorLine label="Settings" result={state.settings} />
          <ErrorLine label="Data sources" result={state.sources} />
          <ErrorLine label="Cache" result={state.cache} />
        </section>
      </section>
    </AppShell>
  );
}
