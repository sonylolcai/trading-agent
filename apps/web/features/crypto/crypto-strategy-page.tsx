'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  CircleDollarSign,
  Database,
  Gauge,
  Info,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Wifi,
} from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api } from '../../lib/api';
import { useI18n } from '../../lib/i18n/context';
import {
  buildCryptoAllocation,
  type CryptoAssetInput,
  type CryptoRegime,
} from '../../lib/crypto-strategy';
import type {
  CryptoBacktestResponse,
  OkxConnectionStatus,
} from '../../types/api';

const INITIAL_ASSETS: CryptoAssetInput[] = [
  { symbol: 'BTC', name: 'Bitcoin', role: '市场基准 / 核心仓', momentum: 0.72, volatility: 0.48, fundingPercentile: 58, aboveEma100: true },
  { symbol: 'ETH', name: 'Ethereum', role: '高流动性次核心', momentum: 0.41, volatility: 0.66, fundingPercentile: 64, aboveEma100: true },
  { symbol: 'BNB', name: 'BNB', role: '交易所生态卫星仓', momentum: 0.27, volatility: 0.58, fundingPercentile: 78, aboveEma100: true },
  { symbol: 'XRP', name: 'XRP', role: '事件型卫星仓', momentum: -0.08, volatility: 0.79, fundingPercentile: 45, aboveEma100: false },
  { symbol: 'SOL', name: 'Solana', role: '高波动成长卫星仓', momentum: 0.55, volatility: 0.91, fundingPercentile: 92, aboveEma100: true },
];

const REGIMES: Array<{ value: CryptoRegime; zh: string; en: string }> = [
  { value: 'risk_on', zh: '进攻', en: 'Risk-on' },
  { value: 'neutral', zh: '中性', en: 'Neutral' },
  { value: 'range', zh: '震荡', en: 'Range' },
  { value: 'risk_off', zh: '防守', en: 'Risk-off' },
  { value: 'crisis', zh: '危机', en: 'Crisis' },
];

const COPY = {
  zh: {
    title: '加密策略',
    heading: '五大加密资产配置实验室',
    intro: '用市场状态、绝对趋势、波动率和资金费率拥挤度生成研究权重。',
    scenario: 'OKX 公开历史行情 · 模拟账户认证可选',
    liveBacktest: '真实行情回测',
    liveBacktestHelp: '使用 OKX UTC 日线；信号在当日收盘生成，从下一日开始持有，包含换仓摩擦。',
    runBacktest: '运行 OKX 回测',
    running: '正在获取与计算…',
    connection: 'OKX 连接',
    checking: '检测中',
    publicReady: '公开行情可用',
    keyMissing: '未配置 Demo Key',
    demoReady: '模拟账户已认证',
    years: '回测年数',
    strategyVersion: '策略版本',
    stable: 'V1 稳定版',
    experimental: 'V2 实验版',
    cost: '单边成本',
    rebalance: '再平衡',
    days: '天',
    result: '策略实际效果',
    resultHelp: '组合净值与 BTC 买入持有基准；回撤已单独标出。',
    totalReturn: '累计收益',
    cagr: '年化收益',
    maxDrawdown: '最大回撤',
    sharpe: '夏普比率',
    strategy: '策略',
    benchmark: 'BTC 基准',
    drawdown: '策略回撤',
    recent: '最近 30% 留出期',
    stress: '双倍交易摩擦',
    v1Compare: '相对 V1 年化',
    emergencyExits: '每日紧急退出',
    rangeDays: '震荡状态天数',
    latest: '最新目标仓位',
    noResult: '运行后显示 OKX 真实历史数据结果。',
    sourceNote: '仅使用已确认收盘的 1Dutc K 线；历史资金费率尚未纳入本版。',
    error: '回测失败',
    regime: '市场状态',
    targetVol: '目标年化波动率',
    reset: '重置场景',
    gross: '风险敞口',
    cash: '现金权重',
    estimatedVol: '预估组合波动',
    selected: '入选资产',
    inputs: '信号输入',
    inputsHelp: '编辑研究输入，权重会立即重算。动量与波动均为小数，例如 0.72 = 72%。',
    asset: '资产',
    momentum: '趋势分数',
    volatility: '年化波动',
    funding: '资金费率分位',
    ema: '高于 EMA100',
    eligible: '状态',
    included: '可配置',
    excluded: '排除',
    allocation: '目标配置',
    allocationHelp: '最多选择三个资产；BTC 上限 50%，其他资产上限 25%。',
    method: '决策链',
    limits: '风险边界',
    note: '页面可读取 OKX 公开行情及只读模拟账户状态。当前没有下单接口，不会产生任何订单。',
    steps: [
      ['01', '状态机', '区分进攻、中性、震荡、防守和危机状态。'],
      ['02', '滞回入场', '突破确认比继续持有使用更严格的条件。'],
      ['03', '每日保护', '趋势破坏、动量恶化或移动保护触发退出。'],
      ['04', '风险配置', '按趋势强度与波动率分配并保留现金。'],
    ],
  },
  en: {
    title: 'Crypto Strategy',
    heading: 'Top-five crypto allocation lab',
    intro: 'Generate research weights from regime, absolute trend, volatility, and funding crowding.',
    scenario: 'OKX public history · demo account auth optional',
    liveBacktest: 'Live-market backtest',
    liveBacktestHelp: 'Uses OKX UTC daily bars. Close-t signals are held from t+1 and trading friction is included.',
    runBacktest: 'Run OKX backtest',
    running: 'Fetching and calculating…',
    connection: 'OKX connection',
    checking: 'Checking',
    publicReady: 'Public market data ready',
    keyMissing: 'Demo key not configured',
    demoReady: 'Demo account authenticated',
    years: 'Backtest years',
    strategyVersion: 'Strategy version',
    stable: 'V1 stable',
    experimental: 'V2 experimental',
    cost: 'One-way cost',
    rebalance: 'Rebalance',
    days: 'days',
    result: 'Observed strategy performance',
    resultHelp: 'Portfolio equity versus BTC buy-and-hold, with strategy drawdown shown separately.',
    totalReturn: 'Total return',
    cagr: 'CAGR',
    maxDrawdown: 'Max drawdown',
    sharpe: 'Sharpe',
    strategy: 'Strategy',
    benchmark: 'BTC benchmark',
    drawdown: 'Strategy drawdown',
    recent: 'Recent 30% holdout',
    stress: 'Double trading friction',
    v1Compare: 'CAGR versus V1',
    emergencyExits: 'Daily emergency exits',
    rangeDays: 'Range-regime days',
    latest: 'Latest target weights',
    noResult: 'Run the backtest to load observed OKX history.',
    sourceNote: 'Uses confirmed 1Dutc candles only; historical funding is not included in this version.',
    error: 'Backtest failed',
    regime: 'Market regime',
    targetVol: 'Target annual volatility',
    reset: 'Reset scenario',
    gross: 'Gross exposure',
    cash: 'Cash weight',
    estimatedVol: 'Estimated volatility',
    selected: 'Selected assets',
    inputs: 'Signal inputs',
    inputsHelp: 'Edit the research inputs to recalculate weights. Values are decimals, so 0.72 means 72%.',
    asset: 'Asset',
    momentum: 'Trend score',
    volatility: 'Annual vol',
    funding: 'Funding percentile',
    ema: 'Above EMA100',
    eligible: 'Status',
    included: 'Eligible',
    excluded: 'Excluded',
    allocation: 'Target allocation',
    allocationHelp: 'Selects at most three assets; BTC is capped at 50% and each other asset at 25%.',
    method: 'Decision chain',
    limits: 'Risk boundaries',
    note: 'The page can read OKX public data and read-only demo account status. There is no order endpoint, so it cannot place orders.',
    steps: [
      ['01', 'State machine', 'Separates risk-on, neutral, range, risk-off, and crisis states.'],
      ['02', 'Entry hysteresis', 'New entries require stronger confirmation than continued holding.'],
      ['03', 'Daily protection', 'Trend, momentum, and trailing protection can force exits.'],
      ['04', 'Risk allocation', 'Weights by trend and volatility, leaving the rest in cash.'],
    ],
  },
} as const;

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatRatio(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2);
}

function linePath(
  values: number[],
  width: number,
  height: number,
  minimum: number,
  maximum: number,
): string {
  const span = Math.max(maximum - minimum, 1e-9);
  return values.map((value, index) => {
    const x = values.length <= 1 ? 0 : index / (values.length - 1) * width;
    const y = height - (value - minimum) / span * height;
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');
}

function PerformanceChart({
  result,
  strategyLabel,
  benchmarkLabel,
  drawdownLabel,
}: {
  result: CryptoBacktestResponse;
  strategyLabel: string;
  benchmarkLabel: string;
  drawdownLabel: string;
}) {
  const width = 960;
  const equityHeight = 220;
  const drawdownHeight = 70;
  const strategy = result.curve.map((point) => point.equity);
  const benchmark = result.curve.map((point) => point.benchmark);
  const drawdowns = result.curve.map((point) => point.drawdown);
  const minimum = Math.min(...strategy, ...benchmark);
  const maximum = Math.max(...strategy, ...benchmark);
  const worstDrawdown = Math.min(...drawdowns, -0.01);

  return (
    <div className="crypto-performance-chart">
      <div className="crypto-chart-legend">
        <span><i className="crypto-chart-key crypto-chart-key--strategy" />{strategyLabel}</span>
        <span><i className="crypto-chart-key crypto-chart-key--benchmark" />{benchmarkLabel}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${equityHeight}`} role="img" aria-label={`${strategyLabel} vs ${benchmarkLabel}`}>
        <path className="crypto-chart-grid" d={`M0,${equityHeight / 2}H${width}`} />
        <path
          className="crypto-chart-line crypto-chart-line--benchmark"
          d={linePath(benchmark, width, equityHeight, minimum, maximum)}
        />
        <path
          className="crypto-chart-line crypto-chart-line--strategy"
          d={linePath(strategy, width, equityHeight, minimum, maximum)}
        />
      </svg>
      <div className="crypto-drawdown-label">{drawdownLabel}</div>
      <svg viewBox={`0 0 ${width} ${drawdownHeight}`} role="img" aria-label={drawdownLabel}>
        <path
          className="crypto-chart-line crypto-chart-line--drawdown"
          d={linePath(drawdowns, width, drawdownHeight, worstDrawdown, 0)}
        />
      </svg>
      <div className="crypto-chart-axis">
        <span>{result.sample.start}</span>
        <span>{result.sample.end}</span>
      </div>
    </div>
  );
}

function reasonLabel(reason: string | null, locale: 'zh' | 'en'): string {
  if (reason === 'below_ema100') {
    return locale === 'zh' ? '低于 EMA100' : 'Below EMA100';
  }
  if (reason === 'momentum_not_positive') {
    return locale === 'zh' ? '趋势非正' : 'Trend not positive';
  }
  if (reason === 'invalid_volatility') {
    return locale === 'zh' ? '波动输入无效' : 'Invalid volatility';
  }
  return locale === 'zh' ? '可配置' : 'Eligible';
}

export function CryptoStrategyPage() {
  const { locale } = useI18n();
  const copy = COPY[locale];
  const [assets, setAssets] = useState<CryptoAssetInput[]>(() => INITIAL_ASSETS.map((asset) => ({ ...asset })));
  const [regime, setRegime] = useState<CryptoRegime>('neutral');
  const [targetVolatility, setTargetVolatility] = useState(0.15);
  const [years, setYears] = useState(5);
  const [strategyVersion, setStrategyVersion] = useState<'1.0' | '2.0'>('1.0');
  const [costBps, setCostBps] = useState(10);
  const [rebalanceDays, setRebalanceDays] = useState(7);
  const [okxStatus, setOkxStatus] = useState<OkxConnectionStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [backtest, setBacktest] = useState<CryptoBacktestResponse | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);

  const allocation = useMemo(
    () => buildCryptoAllocation(assets, regime, targetVolatility),
    [assets, regime, targetVolatility],
  );

  useEffect(() => {
    let active = true;
    api.okxStatus().then((result) => {
      if (!active) {
        return;
      }
      if (result.ok) {
        setOkxStatus(result.data);
      }
      setStatusLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  function updateAsset(symbol: string, patch: Partial<CryptoAssetInput>) {
    setAssets((current) => current.map((asset) => (
      asset.symbol === symbol ? { ...asset, ...patch } : asset
    )));
  }

  function resetScenario() {
    setAssets(INITIAL_ASSETS.map((asset) => ({ ...asset })));
    setRegime('neutral');
    setTargetVolatility(0.15);
  }

  async function runBacktest() {
    setBacktestLoading(true);
    setBacktestError(null);
    const result = await api.cryptoBacktest({
      years,
      target_volatility: targetVolatility,
      cost_bps: costBps,
      rebalance_days: rebalanceDays,
      strategy_version: strategyVersion,
    });
    if (result.ok) {
      setBacktest(result.data);
    } else {
      setBacktestError(result.error);
    }
    setBacktestLoading(false);
  }

  return (
    <AppShell title={copy.title}>
      <section className="crypto-hero">
        <div className="crypto-hero__copy">
          <h2>{copy.heading}</h2>
          <p>{copy.intro}</p>
          <div className="crypto-scenario-note">
            <Info size={15} aria-hidden="true" />
            <span>{copy.scenario}</span>
          </div>
        </div>
        <div className="crypto-summary" aria-label="Allocation summary">
          <div>
            <span>{copy.gross}</span>
            <strong>{formatPercent(allocation.grossExposure)}</strong>
          </div>
          <div>
            <span>{copy.cash}</span>
            <strong>{formatPercent(allocation.cashWeight)}</strong>
          </div>
          <div>
            <span>{copy.estimatedVol}</span>
            <strong>{formatPercent(allocation.estimatedVolatility)}</strong>
          </div>
          <div>
            <span>{copy.selected}</span>
            <strong>{allocation.selectedCount} / 5</strong>
          </div>
        </div>
      </section>

      <section className="panel crypto-live-panel">
        <div className="panel__header">
          <div>
            <h2>{copy.liveBacktest}</h2>
            <p>{copy.liveBacktestHelp}</p>
          </div>
          <div className="crypto-okx-status">
            <Wifi size={15} aria-hidden="true" />
            <div>
              <span>{copy.connection}</span>
              <strong>
                {statusLoading
                  ? copy.checking
                  : okxStatus?.authenticated
                    ? copy.demoReady
                    : okxStatus?.public_api_reachable
                      ? copy.publicReady
                      : locale === 'zh' ? '连接不可用' : 'Unavailable'}
              </strong>
            </div>
            {!statusLoading && okxStatus?.public_api_reachable && (
              <StatusChip tone={okxStatus.authenticated ? 'good' : 'warn'}>
                {okxStatus.authenticated ? 'DEMO' : copy.keyMissing}
              </StatusChip>
            )}
          </div>
        </div>

        <div className="crypto-backtest-controls">
          <label>
            <span>{copy.strategyVersion}</span>
            <select
              value={strategyVersion}
              onChange={(event) => setStrategyVersion(event.target.value as '1.0' | '2.0')}
            >
              <option value="1.0">{copy.stable}</option>
              <option value="2.0">{copy.experimental}</option>
            </select>
          </label>
          <label>
            <span>{copy.years}</span>
            <select value={years} onChange={(event) => setYears(Number(event.target.value))}>
              {[2, 3, 4, 5, 6, 7, 8].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            <span>{copy.targetVol}</span>
            <input
              type="number"
              min="0.05"
              max="0.40"
              step="0.01"
              value={targetVolatility}
              onChange={(event) => setTargetVolatility(Number(event.target.value))}
            />
          </label>
          <label>
            <span>{copy.cost}</span>
            <div className="crypto-input-suffix">
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={costBps}
                onChange={(event) => setCostBps(Number(event.target.value))}
              />
              <span>bps</span>
            </div>
          </label>
          <label>
            <span>{copy.rebalance}</span>
            <div className="crypto-input-suffix">
              <input
                type="number"
                min="1"
                max="30"
                step="1"
                value={rebalanceDays}
                onChange={(event) => setRebalanceDays(Number(event.target.value))}
              />
              <span>{copy.days}</span>
            </div>
          </label>
          <button
            className="crypto-run-button"
            type="button"
            disabled={backtestLoading}
            onClick={runBacktest}
          >
            {backtestLoading
              ? <RefreshCw className="crypto-spin" size={16} aria-hidden="true" />
              : <Play size={16} aria-hidden="true" />}
            <span>{backtestLoading ? copy.running : copy.runBacktest}</span>
          </button>
        </div>

        {backtestError && (
          <div className="crypto-backtest-error" role="alert">
            <strong>{copy.error}</strong>
            <span>{backtestError}</span>
          </div>
        )}

        {!backtest && !backtestLoading && !backtestError && (
          <div className="crypto-backtest-empty">
            <Database size={20} aria-hidden="true" />
            <span>{copy.noResult}</span>
          </div>
        )}

        {backtest && (
          <div className="crypto-backtest-result">
            <div className="crypto-result-heading">
              <div>
                <h3>{copy.result}</h3>
                <p>{copy.resultHelp}</p>
              </div>
              <StatusChip tone={backtest.metrics.total_return >= 0 ? 'good' : 'bad'}>
                V{backtest.strategy.version} · {backtest.sample.start} → {backtest.sample.end}
              </StatusChip>
            </div>

            <div className="crypto-metric-grid">
              <div>
                <span>{copy.totalReturn}</span>
                <strong>{formatPercent(backtest.metrics.total_return)}</strong>
                <small>BTC {formatPercent(backtest.benchmark.total_return)}</small>
              </div>
              <div>
                <span>{copy.cagr}</span>
                <strong>{formatPercent(backtest.metrics.cagr)}</strong>
                <small>BTC {formatPercent(backtest.benchmark.cagr)}</small>
              </div>
              <div>
                <span>{copy.maxDrawdown}</span>
                <strong className="crypto-negative">{formatPercent(backtest.metrics.max_drawdown)}</strong>
                <small>BTC {formatPercent(backtest.benchmark.max_drawdown)}</small>
              </div>
              <div>
                <span>{copy.sharpe}</span>
                <strong>{formatRatio(backtest.metrics.sharpe)}</strong>
                <small>BTC {formatRatio(backtest.benchmark.sharpe)}</small>
              </div>
            </div>

            <PerformanceChart
              result={backtest}
              strategyLabel={copy.strategy}
              benchmarkLabel={copy.benchmark}
              drawdownLabel={copy.drawdown}
            />

            <div className="crypto-validation-grid">
              <div>
                <span>{copy.recent}</span>
                <strong>{formatPercent(backtest.validation.recent_30_pct.cagr)}</strong>
                <small>
                  {copy.maxDrawdown} {formatPercent(backtest.validation.recent_30_pct.max_drawdown)}
                </small>
              </div>
              <div>
                <span>{copy.stress}</span>
                <strong>{formatPercent(backtest.stress.cagr)}</strong>
                <small>
                  {backtest.stress.cost_bps} bps · {copy.maxDrawdown} {formatPercent(backtest.stress.max_drawdown)}
                </small>
              </div>
              <div>
                <span>{locale === 'zh' ? '平均风险敞口' : 'Average gross exposure'}</span>
                <strong>{formatPercent(backtest.metrics.average_gross_exposure ?? 0)}</strong>
                <small>
                  {locale === 'zh' ? '年化换手' : 'Annual turnover'} {formatRatio(backtest.metrics.annual_turnover)}
                </small>
              </div>
              <div>
                <span>{copy.latest}</span>
                <strong>{REGIMES.find((item) => item.value === backtest.latest.regime)?.[locale === 'zh' ? 'zh' : 'en']}</strong>
                <small>
                  {Object.entries(backtest.latest.weights)
                    .map(([symbol, weight]) => `${symbol} ${formatPercent(weight)}`)
                    .join(' · ') || 'CASH 100%'}
                </small>
              </div>
              {backtest.baseline_v1 && (
                <div>
                  <span>{copy.v1Compare}</span>
                  <strong>
                    {formatPercent(backtest.metrics.cagr - backtest.baseline_v1.metrics.cagr)}
                  </strong>
                  <small>V1 {formatPercent(backtest.baseline_v1.metrics.cagr)}</small>
                </div>
              )}
              <div>
                <span>{copy.emergencyExits}</span>
                <strong>{backtest.diagnostics.emergency_exit_count}</strong>
                <small>
                  {Object.entries(backtest.diagnostics.exit_counts)
                    .map(([reason, count]) => `${reason} ${count}`)
                    .join(' · ') || '—'}
                </small>
              </div>
              <div>
                <span>{copy.rangeDays}</span>
                <strong>{backtest.regime_days.range ?? 0}</strong>
                <small>
                  {locale === 'zh' ? '震荡期禁止新开趋势仓' : 'No new trend entries in range'}
                </small>
              </div>
            </div>

            <div className="crypto-yearly-returns">
              {Object.entries(backtest.annual_returns).map(([year, value]) => (
                <div key={year}>
                  <span>{year}</span>
                  <strong className={value < 0 ? 'crypto-negative' : undefined}>
                    {formatPercent(value)}
                  </strong>
                </div>
              ))}
            </div>

            <p className="crypto-source-note">
              <Info size={14} aria-hidden="true" />
              <span>{copy.sourceNote}</span>
            </p>
          </div>
        )}
      </section>

      <div className="crypto-grid">
        <div className="crypto-grid__main">
          <section className="panel">
            <div className="panel__header">
              <div>
                <h2>{copy.inputs}</h2>
                <p>{copy.inputsHelp}</p>
              </div>
              <button className="icon-button" type="button" onClick={resetScenario}>
                <RotateCcw size={15} aria-hidden="true" />
                <span>{copy.reset}</span>
              </button>
            </div>

            <div className="crypto-controls">
              <fieldset className="crypto-control-group">
                <legend>{copy.regime}</legend>
                <div className="crypto-regime-switch">
                  {REGIMES.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      aria-pressed={regime === item.value}
                      onClick={() => setRegime(item.value)}
                    >
                      {locale === 'zh' ? item.zh : item.en}
                    </button>
                  ))}
                </div>
              </fieldset>

              <label className="crypto-vol-control">
                <span>{copy.targetVol}</span>
                <strong>{formatPercent(targetVolatility)}</strong>
                <input
                  type="range"
                  min="0.08"
                  max="0.24"
                  step="0.01"
                  value={targetVolatility}
                  onChange={(event) => setTargetVolatility(Number(event.target.value))}
                />
              </label>
            </div>

            <div className="crypto-table-wrap">
              <table className="crypto-table">
                <thead>
                  <tr>
                    <th>{copy.asset}</th>
                    <th>{copy.momentum}</th>
                    <th>{copy.volatility}</th>
                    <th>{copy.funding}</th>
                    <th>{copy.ema}</th>
                    <th>{copy.eligible}</th>
                  </tr>
                </thead>
                <tbody>
                  {allocation.assets.map((asset) => (
                    <tr key={asset.symbol}>
                      <td>
                        <div className="crypto-asset-name">
                          <strong>{asset.symbol}</strong>
                          <span>{asset.name}</span>
                        </div>
                      </td>
                      <td>
                        <input
                          className="crypto-number-input"
                          aria-label={`${asset.symbol} ${copy.momentum}`}
                          type="number"
                          min="-1"
                          max="1"
                          step="0.01"
                          value={asset.momentum}
                          onChange={(event) => updateAsset(asset.symbol, { momentum: Number(event.target.value) })}
                        />
                      </td>
                      <td>
                        <input
                          className="crypto-number-input"
                          aria-label={`${asset.symbol} ${copy.volatility}`}
                          type="number"
                          min="0.01"
                          max="2"
                          step="0.01"
                          value={asset.volatility}
                          onChange={(event) => updateAsset(asset.symbol, { volatility: Number(event.target.value) })}
                        />
                      </td>
                      <td>
                        <input
                          className="crypto-number-input"
                          aria-label={`${asset.symbol} ${copy.funding}`}
                          type="number"
                          min="0"
                          max="100"
                          step="1"
                          value={asset.fundingPercentile}
                          onChange={(event) => updateAsset(asset.symbol, { fundingPercentile: Number(event.target.value) })}
                        />
                      </td>
                      <td>
                        <label className="crypto-checkbox">
                          <input
                            type="checkbox"
                            checked={asset.aboveEma100}
                            onChange={(event) => updateAsset(asset.symbol, { aboveEma100: event.target.checked })}
                          />
                          <span>{asset.aboveEma100 ? (locale === 'zh' ? '是' : 'Yes') : (locale === 'zh' ? '否' : 'No')}</span>
                        </label>
                      </td>
                      <td>
                        <StatusChip tone={asset.eligible ? 'good' : 'warn'}>
                          {asset.eligible ? copy.included : reasonLabel(asset.exclusionReason, locale)}
                        </StatusChip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel__header">
              <div>
                <h2>{copy.allocation}</h2>
                <p>{copy.allocationHelp}</p>
              </div>
              <StatusChip tone={regime === 'crisis' ? 'bad' : regime === 'risk_on' ? 'good' : 'warn'}>
                {REGIMES.find((item) => item.value === regime)?.[locale === 'zh' ? 'zh' : 'en']}
              </StatusChip>
            </div>

            <div className="crypto-allocation-list">
              {allocation.assets.map((asset) => (
                <div className="crypto-allocation-row" key={asset.symbol}>
                  <div className="crypto-allocation-row__label">
                    <strong>{asset.symbol}</strong>
                    <span>{asset.role}</span>
                  </div>
                  <div className="crypto-weight-track" aria-label={`${asset.symbol} ${formatPercent(asset.weight)}`}>
                    <span style={{ width: formatPercent(asset.weight) }} />
                  </div>
                  <strong>{formatPercent(asset.weight)}</strong>
                </div>
              ))}
              <div className="crypto-allocation-row crypto-allocation-row--cash">
                <div className="crypto-allocation-row__label">
                  <strong>CASH</strong>
                  <span>{locale === 'zh' ? '风险缓冲' : 'Risk buffer'}</span>
                </div>
                <div className="crypto-weight-track" aria-label={`Cash ${formatPercent(allocation.cashWeight)}`}>
                  <span style={{ width: formatPercent(allocation.cashWeight) }} />
                </div>
                <strong>{formatPercent(allocation.cashWeight)}</strong>
              </div>
            </div>
          </section>
        </div>

        <aside className="crypto-grid__side">
          <section className="panel crypto-method">
            <div className="panel__header">
              <div>
                <h2>{copy.method}</h2>
              </div>
              <Activity size={17} aria-hidden="true" />
            </div>
            <ol>
              {copy.steps.map(([index, title, description]) => (
                <li key={index}>
                  <span>{index}</span>
                  <div>
                    <strong>{title}</strong>
                    <p>{description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="panel crypto-risk">
            <div className="panel__header">
              <div>
                <h2>{copy.limits}</h2>
              </div>
              <ShieldCheck size={17} aria-hidden="true" />
            </div>
            <div className="crypto-risk__line">
              <Gauge size={16} aria-hidden="true" />
              <span>{locale === 'zh' ? '状态敞口上限' : 'Regime gross cap'}</span>
              <strong>{formatPercent(allocation.grossCap)}</strong>
            </div>
            <div className="crypto-risk__line">
              <CircleDollarSign size={16} aria-hidden="true" />
              <span>{locale === 'zh' ? '未配置资金' : 'Unallocated capital'}</span>
              <strong>{formatPercent(allocation.cashWeight)}</strong>
            </div>
            <p>{copy.note}</p>
          </section>
        </aside>
      </div>
    </AppShell>
  );
}
