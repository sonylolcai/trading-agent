'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw, RotateCcw } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import type {
  BacktestRebuildResponse,
  RollingBacktestComparisonResponse,
  SetupStatsResponse,
  VolumeContextName,
} from '../../types/api';

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

function formatDelta(value: number): string {
  return `${value > 0 ? '+' : ''}${formatNumber(value)}`;
}

export function BacktestPage() {
  const [stats, setStats] = useState<ApiResult<SetupStatsResponse> | null>(null);
  const [comparison, setComparison] = useState<ApiResult<RollingBacktestComparisonResponse> | null>(null);
  const [rebuild, setRebuild] = useState<ApiResult<BacktestRebuildResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);

  async function load() {
    setLoading(true);
    const [nextStats, nextComparison] = await Promise.all([
      api.setupStats(),
      api.rollingBacktestComparison({ window: 100 }),
    ]);
    setStats(nextStats);
    setComparison(nextComparison);
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
  const comparisonData = comparison?.ok ? comparison.data : null;
  const cautionReasons = comparisonData
    ? Object.entries(comparisonData.volume_assisted.volume_caution_reasons)
    : [];
  const confirmedCandidate = comparisonData?.volume_confirmed ?? null;
  const timeExitCandidate = comparisonData?.volume_confirmed_time_exit ?? null;
  const volumeContextRows = comparisonData
    ? ([
      ['confirmed', 'Confirmed'],
      ['caution', 'Caution'],
      ['neutral', 'Neutral'],
      ['unavailable', 'Volume unavailable'],
    ] as const).map(([context, label]) => ({
      context,
      label,
      metrics: comparisonData.volume_contexts[context as VolumeContextName],
    }))
    : [];

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

      <section className="panel">
        <div className="panel__header">
          <div>
            <h2>Price Action vs Hard Volume Filter</h2>
            <p>Same cached K-lines, risk profile, entries, stops, targets, and simulator.</p>
          </div>
          <StatusChip tone={comparison?.ok ? 'good' : 'bad'}>
            {comparison?.ok ? 'ready' : comparison ? 'offline' : 'loading'}
          </StatusChip>
        </div>

        {!comparison?.ok && comparison ? (
          <div className="error-block">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>Rolling comparison unavailable: {comparison.error}</span>
          </div>
        ) : null}

        {comparisonData ? (
          <>
            <div className="metrics-grid">
              <div>
                <span>Symbol / timeframe</span>
                <strong>{comparisonData.symbol} · {comparisonData.timeframe}</strong>
              </div>
              <div>
                <span>Cached-bar window</span>
                <strong>{comparisonData.window}</strong>
              </div>
              <div>
                <span>Volume cautions skipped</span>
                <strong>{comparisonData.volume_assisted.skipped_volume_caution}</strong>
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Price only</th>
                    <th>Volume assisted</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['Trade signals', comparisonData.price_only.trade_signals, comparisonData.volume_assisted.trade_signals, comparisonData.delta.trade_signals],
                    ['Completed trades', comparisonData.price_only.completed_trades, comparisonData.volume_assisted.completed_trades, comparisonData.delta.completed_trades],
                    ['Wins', comparisonData.price_only.wins, comparisonData.volume_assisted.wins, comparisonData.delta.wins],
                    ['Losses', comparisonData.price_only.losses, comparisonData.volume_assisted.losses, comparisonData.delta.losses],
                    ['Win rate', comparisonData.price_only.win_rate_pct, comparisonData.volume_assisted.win_rate_pct, comparisonData.volume_assisted.win_rate_pct - comparisonData.price_only.win_rate_pct],
                    ['Expectancy R', comparisonData.price_only.expectancy_r, comparisonData.volume_assisted.expectancy_r, comparisonData.delta.expectancy_r],
                    ['Total R', comparisonData.price_only.total_r, comparisonData.volume_assisted.total_r, comparisonData.delta.total_r],
                    ['Max drawdown R', comparisonData.price_only.max_drawdown_r, comparisonData.volume_assisted.max_drawdown_r, comparisonData.delta.max_drawdown_r],
                  ].map(([label, baseline, assisted, delta]) => (
                    <tr key={String(label)}>
                      <td>{label}</td>
                      <td>{formatNumber(Number(baseline))}</td>
                      <td>{formatNumber(Number(assisted))}</td>
                      <td>{formatDelta(Number(delta))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {confirmedCandidate ? (
              <>
                <h3>Volume-Confirmed Candidate</h3>
                <p>Research-only: keeps price signals only when volume and closing strength confirm the breakout.</p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Price only</th>
                        <th>Confirmed only</th>
                        <th>Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['Trade signals', comparisonData.price_only.trade_signals, confirmedCandidate.trade_signals],
                        ['Completed trades', comparisonData.price_only.completed_trades, confirmedCandidate.completed_trades],
                        ['Win rate', comparisonData.price_only.win_rate_pct, confirmedCandidate.win_rate_pct],
                        ['Expectancy R', comparisonData.price_only.expectancy_r, confirmedCandidate.expectancy_r],
                        ['Total R', comparisonData.price_only.total_r, confirmedCandidate.total_r],
                        ['Max drawdown R', comparisonData.price_only.max_drawdown_r, confirmedCandidate.max_drawdown_r],
                      ].map(([label, baseline, candidate]) => (
                        <tr key={String(label)}>
                          <td>{label}</td>
                          <td>{formatNumber(Number(baseline))}</td>
                          <td>{formatNumber(Number(candidate))}</td>
                          <td>{formatDelta(Number(candidate) - Number(baseline))}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            {confirmedCandidate && timeExitCandidate ? (
              <>
                <h3>10-Bar Time-Exit Benchmark</h3>
                <p>Research-only benchmark, not a selected default: uses the same volume-confirmed entries and initial stops; if neither stop nor target is hit, it exits at the close of bar 10.</p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Confirmed fixed exit</th>
                        <th>Confirmed time exit</th>
                        <th>Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['Trade signals', confirmedCandidate.trade_signals, timeExitCandidate.trade_signals],
                        ['Completed trades', confirmedCandidate.completed_trades, timeExitCandidate.completed_trades],
                        ['Win rate', confirmedCandidate.win_rate_pct, timeExitCandidate.win_rate_pct],
                        ['Expectancy R', confirmedCandidate.expectancy_r, timeExitCandidate.expectancy_r],
                        ['Total R', confirmedCandidate.total_r, timeExitCandidate.total_r],
                        ['Max drawdown R', confirmedCandidate.max_drawdown_r, timeExitCandidate.max_drawdown_r],
                      ].map(([label, baseline, candidate]) => (
                        <tr key={String(label)}>
                          <td>{label}</td>
                          <td>{formatNumber(Number(baseline))}</td>
                          <td>{formatNumber(Number(candidate))}</td>
                          <td>{formatDelta(Number(candidate) - Number(baseline))}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            <h3>Volume Context Audit</h3>
            <p>Every price-action signal is measured here; these labels do not alter entries, exits, or position size.</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Context</th>
                    <th>Signals</th>
                    <th>Completed</th>
                    <th>Win rate</th>
                    <th>Expectancy R</th>
                    <th>Total R</th>
                  </tr>
                </thead>
                <tbody>
                  {volumeContextRows.map(({ context, label, metrics }) => (
                    <tr key={context}>
                      <td>{label}</td>
                      <td>{metrics.trade_signals}</td>
                      <td>{metrics.completed_trades}</td>
                      <td>{formatNumber(metrics.win_rate_pct)}%</td>
                      <td>{formatNumber(metrics.expectancy_r)}</td>
                      <td>{formatNumber(metrics.total_r)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {cautionReasons.length > 0 ? (
              <div className="notice-block">
                Volume-assisted filters: {cautionReasons.map(([reason, count]) => `${reason} (${count})`).join(', ')}
              </div>
            ) : (
              <div className="empty-state">No volume caution filter was triggered in this cached window.</div>
            )}
          </>
        ) : null}
      </section>
    </AppShell>
  );
}
