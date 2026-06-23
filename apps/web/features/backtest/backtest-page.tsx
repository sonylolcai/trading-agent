'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw, RotateCcw } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import type { BacktestRebuildResponse, SetupStatsResponse } from '../../types/api';

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

export function BacktestPage() {
  const [stats, setStats] = useState<ApiResult<SetupStatsResponse> | null>(null);
  const [rebuild, setRebuild] = useState<ApiResult<BacktestRebuildResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);

  async function load() {
    setLoading(true);
    setStats(await api.setupStats());
    setLoading(false);
  }

  async function rebuildStats() {
    setRebuilding(true);
    const result = await api.rebuildSetupStats();
    setRebuild(result);
    if (result.ok) {
      setStats(await api.setupStats());
    }
    setRebuilding(false);
  }

  useEffect(() => {
    void load();
  }, []);

  const rows = useMemo(() => (stats?.ok ? stats.data.rows : []), [stats]);

  return (
    <AppShell title="Backtest">
      <section className="panel">
        <div className="panel__header">
          <div>
            <h2>Setup Statistics</h2>
            <p>{rows.length} setup buckets from the local stats ledger</p>
          </div>
          <div className="toolbar">
            <StatusChip tone={stats?.ok ? 'good' : 'bad'}>{stats?.ok ? 'ready' : 'offline'}</StatusChip>
            <button className="icon-button" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh setup statistics">
              <RefreshCw size={15} aria-hidden="true" />
              <span>{loading ? 'Loading' : 'Refresh'}</span>
            </button>
            <button className="icon-button" type="button" onClick={() => void rebuildStats()} disabled={rebuilding} aria-label="Rebuild setup statistics">
              <RotateCcw size={15} aria-hidden="true" />
              <span>{rebuilding ? 'Rebuilding' : 'Rebuild'}</span>
            </button>
          </div>
        </div>

        {!stats?.ok && stats ? (
          <div className="error-block">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>Setup stats API unavailable: {stats.error}</span>
          </div>
        ) : null}

        {rebuild?.ok ? (
          <div className="metrics-grid">
            <div>
              <span>Records scanned</span>
              <strong>{rebuild.data.records_scanned}</strong>
            </div>
            <div>
              <span>Trade signals</span>
              <strong>{rebuild.data.trade_signals}</strong>
            </div>
            <div>
              <span>Completed trades</span>
              <strong>{rebuild.data.completed_trades}</strong>
            </div>
            <div>
              <span>Setup buckets</span>
              <strong>{rebuild.data.setup_buckets}</strong>
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <span>Output path</span>
              <strong>{rebuild.data.output_path}</strong>
            </div>
          </div>
        ) : null}

        {rebuild && !rebuild.ok ? (
          <div className="error-block">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>Rebuild failed: {rebuild.error}</span>
          </div>
        ) : null}

        {rows.length === 0 ? (
          <div className="empty-state">No setup statistics returned.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Setup key</th>
                  <th>Samples</th>
                  <th>Wins</th>
                  <th>Losses</th>
                  <th>Win rate</th>
                  <th>Expectancy R</th>
                  <th>Total R</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.setup_key}>
                    <td>{row.setup_key}</td>
                    <td>{row.sample_count}</td>
                    <td>{row.wins}</td>
                    <td>{row.losses}</td>
                    <td>{formatNumber(row.win_rate_pct)}%</td>
                    <td>{formatNumber(row.expectancy_r)}</td>
                    <td>{formatNumber(row.total_r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
