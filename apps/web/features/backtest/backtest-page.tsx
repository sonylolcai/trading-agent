'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw, RotateCcw, Search, TrendingUp } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import { useI18n } from '../../lib/i18n/context';
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
  const { t, locale, translateLabel } = useI18n();
  const [stats, setStats] = useState<ApiResult<SetupStatsResponse> | null>(null);
  const [comparison, setComparison] = useState<ApiResult<RollingBacktestComparisonResponse> | null>(null);
  const [rebuild, setRebuild] = useState<ApiResult<BacktestRebuildResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [setupSearch, setSetupSearch] = useState('');

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

  const filteredRows = useMemo(() => {
    if (!setupSearch) return rows;
    return rows.filter((r) => r.setup_key.toLowerCase().includes(setupSearch.toLowerCase()));
  }, [rows, setupSearch]);

  const summary = useMemo(() => {
    if (rows.length === 0) return null;
    const totalSamples = rows.reduce((acc, r) => acc + r.sample_count, 0);
    const totalWins = rows.reduce((acc, r) => acc + r.wins, 0);
    const totalLosses = rows.reduce((acc, r) => acc + r.losses, 0);
    const winRate = totalWins + totalLosses > 0 ? (totalWins / (totalWins + totalLosses)) * 100 : 0;
    const totalR = rows.reduce((acc, r) => acc + r.total_r, 0);
    const avgExpectancy = totalSamples > 0 ? rows.reduce((acc, r) => acc + r.expectancy_r * r.sample_count, 0) / totalSamples : 0;
    return { totalSamples, totalWins, totalLosses, winRate, totalR, avgExpectancy };
  }, [rows]);

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
    <AppShell title={t.navBacktest}>
      <section className="panel">
        <div className="panel__header">
          <div>
            <h2>{t.backtestTitle}</h2>
            <p>{rows.length} {t.backtestSub}</p>
          </div>
          <div className="toolbar">
            <StatusChip tone={stats?.ok ? 'good' : 'bad'}>{stats?.ok ? 'ready' : 'offline'}</StatusChip>
            <button className="icon-button" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh setup statistics">
              <RefreshCw size={15} aria-hidden="true" />
              <span>{loading ? t.loading : t.refresh}</span>
            </button>
            <button className="icon-button" type="button" onClick={() => void rebuildStats()} disabled={rebuilding} aria-label="Rebuild setup statistics">
              <RotateCcw size={15} aria-hidden="true" />
              <span>{rebuilding ? t.rebuilding : t.rebuild}</span>
            </button>
          </div>
        </div>

        {/* Hero KPI Summary Banner */}
        {summary && (
          <div className="backtest-hero-grid">
            <div className="backtest-hero-card">
              <span className="hero-label">{t.totalSamples}</span>
              <strong className="hero-value">{summary.totalSamples}</strong>
              <span className="hero-sub">{rows.length} {t.uniqueSetups}</span>
            </div>
            <div className="backtest-hero-card">
              <span className="hero-label">{t.aggregateWinRate}</span>
              <strong className={`hero-value ${summary.winRate >= 50 ? 'text-good' : 'text-warn'}`}>
                {summary.winRate.toFixed(1)}%
              </strong>
              <span className="hero-sub">{summary.totalWins} {locale === 'zh' ? '胜' : 'W'} / {summary.totalLosses} {locale === 'zh' ? '负' : 'L'}</span>
            </div>
            <div className="backtest-hero-card">
              <span className="hero-label">{t.cumulativeTotalR}</span>
              <strong className={`hero-value ${summary.totalR >= 0 ? 'text-good' : 'text-bad'}`}>
                {formatDelta(summary.totalR)}R
              </strong>
              <span className="hero-sub">{t.acrossAllSetups}</span>
            </div>
            <div className="backtest-hero-card">
              <span className="hero-label">{t.weightedExpectancy}</span>
              <strong className={`hero-value ${summary.avgExpectancy >= 0 ? 'text-good' : 'text-warn'}`}>
                {formatDelta(summary.avgExpectancy)}R
              </strong>
              <span className="hero-sub">{t.avgPerTrade}</span>
            </div>
          </div>
        )}

        {/* Search Input */}
        <div className="backtest-search-row">
          <div className="backtest-search-wrap">
            <Search size={14} className="text-muted" />
            <input
              type="text"
              placeholder={t.searchSetupPlaceholder}
              value={setupSearch}
              onChange={(e) => setSetupSearch(e.target.value)}
              className="backtest-search-input"
            />
          </div>
          <span className="backtest-count-badge">{t.showingSetups} {filteredRows.length} / {rows.length} {t.setupsCount}</span>
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

        {filteredRows.length === 0 ? (
          <div className="empty-state">
            {rows.length === 0 ? (locale === 'zh' ? '暂无 Setup 形态数据。' : 'No setup statistics returned.') : (locale === 'zh' ? '无匹配的 Setup 形态记录。' : 'No setup statistics match current filter.')}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{translateLabel('Setup key')}</th>
                  <th>{translateLabel('Samples')}</th>
                  <th>{translateLabel('Wins')}</th>
                  <th>{translateLabel('Losses')}</th>
                  <th>{t.winRate}</th>
                  <th>{t.expectancyR}</th>
                  <th>{t.totalR}</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.setup_key}>
                    <td><span className="setup-key-badge">{row.setup_key}</span></td>
                    <td className="tabular-num">{row.sample_count}</td>
                    <td className="tabular-num text-good">{row.wins}</td>
                    <td className="tabular-num text-bad">{row.losses}</td>
                    <td>
                      <div className="win-rate-cell">
                        <div className="win-rate-track">
                          <div
                            className={`win-rate-fill ${row.win_rate_pct >= 50 ? 'win-rate-fill--good' : 'win-rate-fill--warn'}`}
                            style={{ width: `${Math.min(row.win_rate_pct, 100)}%` }}
                          />
                        </div>
                        <span className="tabular-num">{formatNumber(row.win_rate_pct)}%</span>
                      </div>
                    </td>
                    <td>
                      <span className={`r-multiple-pill ${row.expectancy_r > 0 ? 'r-multiple-pill--pos' : row.expectancy_r < 0 ? 'r-multiple-pill--neg' : ''}`}>
                        {formatDelta(row.expectancy_r)}R
                      </span>
                    </td>
                    <td>
                      <span className={`r-multiple-pill ${row.total_r > 0 ? 'r-multiple-pill--pos' : row.total_r < 0 ? 'r-multiple-pill--neg' : ''}`}>
                        {formatDelta(row.total_r)}R
                      </span>
                    </td>
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
            <h2>{t.priceVsVolume}</h2>
            <p>{t.priceVsVolumeSub}</p>
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
                <span>{locale === 'zh' ? '标的 / 周期' : 'Symbol / timeframe'}</span>
                <strong>{comparisonData.symbol} · {comparisonData.timeframe}</strong>
              </div>
              <div>
                <span>{locale === 'zh' ? 'K线回测窗口' : 'Cached-bar window'}</span>
                <strong>{comparisonData.window}</strong>
              </div>
              <div>
                <span>{locale === 'zh' ? '成交量预警跳过' : 'Volume cautions skipped'}</span>
                <strong>{comparisonData.volume_assisted.skipped_volume_caution}</strong>
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t.metricLabel}</th>
                    <th>{t.priceOnly}</th>
                    <th>{t.volumeAssisted}</th>
                    <th>{t.deltaLabel}</th>
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
                  ].map(([label, baseline, assisted, delta]) => {
                    const dVal = Number(delta);
                    return (
                      <tr key={String(label)}>
                        <td>{translateLabel(String(label))}</td>
                        <td className="tabular-num">{formatNumber(Number(baseline))}</td>
                        <td className="tabular-num">{formatNumber(Number(assisted))}</td>
                        <td>
                          <span className={`delta-pill ${dVal > 0 ? 'delta-pill--pos' : dVal < 0 ? 'delta-pill--neg' : 'delta-pill--zero'}`}>
                            {formatDelta(dVal)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {confirmedCandidate ? (
              <>
                <h3>{t.volumeConfirmedTitle}</h3>
                <p>{t.volumeConfirmedDesc}</p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t.metricLabel}</th>
                        <th>{t.priceOnly}</th>
                        <th>{t.confirmedOnly}</th>
                        <th>{t.deltaLabel}</th>
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
                      ].map(([label, baseline, candidate]) => {
                        const dVal = Number(candidate) - Number(baseline);
                        return (
                          <tr key={String(label)}>
                            <td>{translateLabel(String(label))}</td>
                            <td className="tabular-num">{formatNumber(Number(baseline))}</td>
                            <td className="tabular-num">{formatNumber(Number(candidate))}</td>
                            <td>
                              <span className={`delta-pill ${dVal > 0 ? 'delta-pill--pos' : dVal < 0 ? 'delta-pill--neg' : 'delta-pill--zero'}`}>
                                {formatDelta(dVal)}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            {confirmedCandidate && timeExitCandidate ? (
              <>
                <h3>{t.timeExitTitle}</h3>
                <p>{t.timeExitDesc}</p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t.metricLabel}</th>
                        <th>{t.confirmedFixed}</th>
                        <th>{t.confirmedTime}</th>
                        <th>{t.deltaLabel}</th>
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
                      ].map(([label, baseline, candidate]) => {
                        const dVal = Number(candidate) - Number(baseline);
                        return (
                          <tr key={String(label)}>
                            <td>{translateLabel(String(label))}</td>
                            <td className="tabular-num">{formatNumber(Number(baseline))}</td>
                            <td className="tabular-num">{formatNumber(Number(candidate))}</td>
                            <td>
                              <span className={`delta-pill ${dVal > 0 ? 'delta-pill--pos' : dVal < 0 ? 'delta-pill--neg' : 'delta-pill--zero'}`}>
                                {formatDelta(dVal)}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            <h3>{t.volumeAuditTitle}</h3>
            <p>{t.volumeAuditDesc}</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t.contextLabel}</th>
                    <th>{t.signalsLabel}</th>
                    <th>{t.completedLabel}</th>
                    <th>{t.winRate}</th>
                    <th>{t.expectancyR}</th>
                    <th>{t.totalR}</th>
                  </tr>
                </thead>
                <tbody>
                  {volumeContextRows.map(({ context, label, metrics }) => (
                    <tr key={context}>
                      <td>{translateLabel(label)}</td>
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
                {locale === 'zh' ? '成交量辅助过滤器: ' : 'Volume-assisted filters: '}
                {cautionReasons.map(([reason, count]) => `${translateLabel(reason)} (${count})`).join(', ')}
              </div>
            ) : (
              <div className="empty-state">
                {locale === 'zh' ? '在当前缓存窗口内未触发任何成交量预警过滤。' : 'No volume caution filter was triggered in this cached window.'}
              </div>
            )}
          </>
        ) : null}
      </section>
    </AppShell>
  );
}
