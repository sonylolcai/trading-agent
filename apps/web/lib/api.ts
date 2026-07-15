import type {
  AnalysisStartResponse,
  AnalysisStatusResponse,
  BacktestRebuildResponse,
  DataSourcesResponse,
  KlineCacheResponse,
  MarketSnapshotResponse,
  MarketSelectionRequest,
  RecordsResponse,
  RiskProfileRequest,
  RollingBacktestResponse,
  SettingsPayload,
  SetupStatsResponse,
  TimeframesResponse,
} from '../types/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_PA_API_BASE_URL ?? 'http://127.0.0.1:8765';

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: 'no-store',
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === 'string') {
          detail = body.detail;
        }
      } catch {
        // Keep the HTTP status text when the body is not JSON.
      }
      return { ok: false, error: detail || `HTTP ${response.status}`, status: response.status };
    }

    return { ok: true, data: (await response.json()) as T };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to reach IQ API';
    return { ok: false, error: message };
  }
}

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : '';
}

export const api = {
  settings: () => request<SettingsPayload>('/api/settings'),
  updateMarketSelection: (payload: MarketSelectionRequest) =>
    request<SettingsPayload>('/api/settings/market', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  updateRiskProfile: (payload: RiskProfileRequest) =>
    request<SettingsPayload>('/api/settings/risk-profile', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  dataSources: () => request<DataSourcesResponse>('/api/data-sources'),
  timeframes: (source: string) => request<TimeframesResponse>(`/api/timeframes?source=${encodeURIComponent(source)}`),
  klineCache: () => request<KlineCacheResponse>('/api/kline-cache'),
  fetchKlines: (payload: MarketSelectionRequest) =>
    request<KlineCacheResponse>('/api/market/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  snapshot: () => request<MarketSnapshotResponse>('/api/market/snapshot?bars=100&include_forming=false'),
  records: () => request<RecordsResponse>('/api/records'),
  startAnalysis: () => request<AnalysisStartResponse>('/api/analysis', { method: 'POST' }),
  analysisStatus: (id: string) => request<AnalysisStatusResponse>(`/api/analysis/${encodeURIComponent(id)}`),
  cancelAnalysis: (id: string) => request<AnalysisStatusResponse>(`/api/analysis/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  rebuildSetupStats: () => request<BacktestRebuildResponse>('/api/backtest/rebuild-setup-stats', { method: 'POST' }),
  setupStats: () => request<SetupStatsResponse>('/api/backtest/setup-stats'),
  rollingBacktestSummary: (payload?: MarketSelectionRequest & { window?: number }) =>
    request<RollingBacktestResponse>(
      `/api/backtest/rolling-summary${queryString({
        source: payload?.source,
        symbol: payload?.symbol,
        timeframe: payload?.timeframe,
        window: payload?.window,
      })}`,
    ),
};

export function analysisEventsUrl(id: string): string {
  return `${API_BASE_URL}/api/analysis/${encodeURIComponent(id)}/events`;
}
