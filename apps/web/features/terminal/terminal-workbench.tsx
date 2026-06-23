'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Database, KeyRound, RefreshCw } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import type { DataSourcesResponse, KlineCacheResponse, MarketSnapshotResponse, SettingsPayload } from '../../types/api';
import { KlineChartPreview } from '../chart/kline-chart-preview';

type TerminalState = {
  settings: ApiResult<SettingsPayload> | null;
  sources: ApiResult<DataSourcesResponse> | null;
  cache: ApiResult<KlineCacheResponse> | null;
  snapshot: ApiResult<MarketSnapshotResponse> | null;
};

const emptyState: TerminalState = {
  settings: null,
  sources: null,
  cache: null,
  snapshot: null,
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

export function TerminalWorkbench() {
  const [state, setState] = useState<TerminalState>(emptyState);
  const [loading, setLoading] = useState(true);

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

  const settingsData = state.settings?.ok ? state.settings.data : undefined;
  const providerKey = readNestedString(settingsData, ['provider', 'api_key']);
  const currentSource = state.cache?.ok ? state.cache.data.source : readNestedString(settingsData, ['general', 'last_data_source']);
  const currentSymbol = state.cache?.ok ? state.cache.data.symbol : readNestedString(settingsData, ['general', 'last_symbol']);
  const currentTimeframe = state.cache?.ok ? state.cache.data.timeframe : readNestedString(settingsData, ['general', 'last_timeframe']);
  const snapshotFrame = state.snapshot?.ok ? state.snapshot.data.frame : undefined;
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
        </div>

        <section className="panel panel--chart">
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

        <section className="panel panel--side">
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
          </div>
          <ErrorLine label="Settings" result={state.settings} />
          <ErrorLine label="Data sources" result={state.sources} />
          <ErrorLine label="Cache" result={state.cache} />
        </section>
      </section>
    </AppShell>
  );
}
