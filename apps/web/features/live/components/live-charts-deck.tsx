'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AreaChart, BarChart2, Clock, Database, HardDrive, RefreshCw, Sliders, Zap } from 'lucide-react';

import {
  createChart,
  CandlestickSeries,
  LineSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { api } from '../../../lib/api';
import { useI18n } from '../../../lib/i18n/context';
import type { OrderBookData, TradeItem } from '../../../lib/market-stream/types';


interface LiveChartsDeckProps {
  symbol: string;
  trades: TradeItem[];
  orderBook: OrderBookData;
  latestPrice: number;
  timeframe?: Timeframe;
  onTimeframeChange?: (tf: Timeframe) => void;
}

type ChartTab = 'kline' | 'depth';
export type Timeframe = '1m' | '15m' | '30m' | '1h' | '4h' | '1d';

export interface TimeframeConfig {
  value: Timeframe;
  label: string;
  intervalSec: number;
  binanceInterval: string;
  volatility: number;
}

export const TIMEFRAME_OPTIONS: TimeframeConfig[] = [
  { value: '1m', label: '1分', intervalSec: 60, binanceInterval: '1m', volatility: 0.0015 },
  { value: '15m', label: '15分', intervalSec: 900, binanceInterval: '15m', volatility: 0.004 },
  { value: '30m', label: '30分', intervalSec: 1800, binanceInterval: '30m', volatility: 0.006 },
  { value: '1h', label: '1小时', intervalSec: 3600, binanceInterval: '1h', volatility: 0.009 },
  { value: '4h', label: '4小时', intervalSec: 14400, binanceInterval: '4h', volatility: 0.018 },
  { value: '1d', label: '日线 (1D)', intervalSec: 86400, binanceInterval: '1d', volatility: 0.035 },
];

const SYSTEM_SANS_FONT = "var(--sans), -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif";

function generateSyntheticKlines(
  timeframeCfg: TimeframeConfig,
  basePrice: number,
  count = 120,
) {
  const nowSec = Math.floor(Date.now() / 1000);
  const { intervalSec, volatility } = timeframeCfg;
  const currentBarTime = Math.floor(nowSec / intervalSec) * intervalSec;

  const candles = [];
  let p = basePrice * (1 - (volatility * count) / 3.5);

  for (let i = count - 1; i >= 0; i--) {
    const time = (currentBarTime - i * intervalSec) as UTCTimestamp;
    const open = p;
    const delta = (Math.random() - 0.49) * (p * volatility);
    const close = open + delta;
    const high = Math.max(open, close) + Math.random() * (p * volatility * 0.6);
    const low = Math.min(open, close) - Math.random() * (p * volatility * 0.6);
    p = close;
    candles.push({ time, open, high, low, close });
  }

  // Ensure last candle close matches current basePrice
  if (candles.length > 0) {
    const last = candles[candles.length - 1];
    last.close = basePrice;
    last.high = Math.max(last.high, basePrice);
    last.low = Math.min(last.low, basePrice);
  }

  return candles;
}

export function LiveChartsDeck({
  symbol,
  trades,
  orderBook,
  latestPrice,
  timeframe: externalTimeframe,
  onTimeframeChange,
}: LiveChartsDeckProps) {
  const { t, locale } = useI18n();
  const [activeTab, setActiveTab] = useState<ChartTab>('kline');
  const [internalTimeframe, setInternalTimeframe] = useState<Timeframe>('1d');
  const [dataLimit, setDataLimit] = useState<number>(1000);
  const [dataSourceInfo, setDataSourceInfo] = useState<string>('backend_cache');
  const [refreshCount, setRefreshCount] = useState<number>(0);
  const [loadingKline, setLoadingKline] = useState(false);
  const [allCandles, setAllCandles] = useState<Array<{ time: UTCTimestamp; open: number; high: number; low: number; close: number }>>([]);

  // Range Brush state (percentages 0 ~ 100)
  const [brushStart, setBrushStart] = useState(65);
  const [brushEnd, setBrushEnd] = useState(100);
  const [isDragging, setIsDragging] = useState<'left' | 'right' | 'window' | null>(null);
  const dragStartXRef = useRef(0);
  const dragStartPctRef = useRef({ start: 65, end: 100 });


  const timeframe = externalTimeframe ?? internalTimeframe;
  const handleSelectTimeframe = (tf: Timeframe) => {
    if (onTimeframeChange) onTimeframeChange(tf);
    else setInternalTimeframe(tf);
  };

  // Lightweight-Charts References
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const currentBarRef = useRef<{
    time: UTCTimestamp;
    open: number;
    high: number;
    low: number;
    close: number;
  } | null>(null);

  const activeTimeframeCfg =
    TIMEFRAME_OPTIONS.find((t) => t.value === timeframe) ?? TIMEFRAME_OPTIONS[5];

  // Initialize and rebuild chart instance
  useEffect(() => {
    if (activeTab !== 'kline' || !chartContainerRef.current) return undefined;

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 350,
      layout: {
        background: { type: ColorType.Solid, color: 'hsl(222, 47%, 8%)' },
        textColor: 'hsl(215, 16%, 65%)',
        fontSize: 11,
        fontFamily: 'JetBrains Mono, Consolas, monospace',
      },
      grid: {
        vertLines: { color: 'hsl(222, 40%, 13%)' },
        horzLines: { color: 'hsl(222, 40%, 13%)' },
      },
      crosshair: {
        vertLine: { color: '#00e5ff', width: 1, style: 3 },
        horzLine: { color: '#00e5ff', width: 1, style: 3 },
      },
      timeScale: {
        borderColor: 'hsl(222, 40%, 20%)',
        timeVisible: activeTimeframeCfg.intervalSec < 86400,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00f59b',
      downColor: '#ff3b69',
      borderVisible: false,
      wickUpColor: '#00f59b',
      wickDownColor: '#ff3b69',
    });

    const emaSeries = chart.addSeries(LineSeries, {
      color: '#00e5ff',
      lineWidth: 2,
      priceLineVisible: false,
      title: 'EMA20',
    });

    chartInstanceRef.current = chart;
    candleSeriesRef.current = candleSeries;
    emaSeriesRef.current = emaSeries;

    // Load K-lines from backend cache store
    let isCancelled = false;
    async function loadData() {
      setLoadingKline(true);
      let candles: Array<{ time: UTCTimestamp; open: number; high: number; low: number; close: number }> = [];

      try {
        const res = await api.cryptoKlines({
          symbol,
          timeframe,
          limit: dataLimit,
        });

        if (res.ok && Array.isArray(res.data?.bars) && res.data.bars.length > 0) {
          candles = res.data.bars.map((item) => ({
            time: item.time as UTCTimestamp,
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close,
          }));
          setDataSourceInfo(res.data.source || 'backend_cache');
        }
      } catch {
        // Fallback to synthetic if backend error
      }

      if (candles.length === 0) {
        candles = generateSyntheticKlines(activeTimeframeCfg, latestPrice || 68000, dataLimit);
        setDataSourceInfo('local_synthetic');
      }

      if (isCancelled) return;

      setAllCandles(candles);

      // Calculate EMA 20
      let ema = candles[0].close;
      const k = 2 / (20 + 1);
      const emaData = candles.map((c) => {
        ema = c.close * k + ema * (1 - k);
        return { time: c.time, value: ema };
      });

      candleSeries.setData(candles);
      emaSeries.setData(emaData);

      if (candles.length > 0) {
        currentBarRef.current = { ...candles[candles.length - 1] };
      }

      // Apply initial brush range (showing the active right-hand window, e.g. 65% - 100%)
      const total = candles.length;
      const from = Math.floor((brushStart / 100) * total);
      const to = Math.min(total - 1, Math.ceil((brushEnd / 100) * total));
      chart.timeScale().setVisibleLogicalRange({ from, to });

      setLoadingKline(false);
    }

    void loadData();

    const handleResize = () => {
      if (chartContainerRef.current && chartInstanceRef.current) {
        chartInstanceRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      isCancelled = true;
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartInstanceRef.current = null;
      candleSeriesRef.current = null;
      emaSeriesRef.current = null;
    };
  }, [activeTab, symbol, timeframe, dataLimit, refreshCount]);


  // Sync brush range to chart timeScale
  const syncBrushToChart = (startPct: number, endPct: number) => {
    if (!chartInstanceRef.current || allCandles.length === 0) return;
    const total = allCandles.length;
    const from = Math.floor((startPct / 100) * total);
    const to = Math.min(total - 1, Math.ceil((endPct / 100) * total));
    chartInstanceRef.current.timeScale().setVisibleLogicalRange({ from, to });
  };

  // Mouse handlers for Range Brush
  const handleBrushMouseDown = (
    e: React.MouseEvent,
    type: 'left' | 'right' | 'window',
  ) => {
    e.preventDefault();
    setIsDragging(type);
    dragStartXRef.current = e.clientX;
    dragStartPctRef.current = { start: brushStart, end: brushEnd };
  };

  useEffect(() => {
    if (!isDragging) return undefined;

    const handleMouseMove = (e: MouseEvent) => {
      const containerW = chartContainerRef.current?.clientWidth || 800;
      const deltaX = e.clientX - dragStartXRef.current;
      const deltaPct = (deltaX / containerW) * 100;

      let nextStart = dragStartPctRef.current.start;
      let nextEnd = dragStartPctRef.current.end;

      if (isDragging === 'left') {
        nextStart = Math.max(0, Math.min(nextEnd - 10, dragStartPctRef.current.start + deltaPct));
      } else if (isDragging === 'right') {
        nextEnd = Math.min(100, Math.max(nextStart + 10, dragStartPctRef.current.end + deltaPct));
      } else if (isDragging === 'window') {
        const span = nextEnd - nextStart;
        nextStart = dragStartPctRef.current.start + deltaPct;
        nextEnd = dragStartPctRef.current.end + deltaPct;

        if (nextStart < 0) {
          nextStart = 0;
          nextEnd = span;
        } else if (nextEnd > 100) {
          nextEnd = 100;
          nextStart = 100 - span;
        }
      }

      setBrushStart(nextStart);
      setBrushEnd(nextEnd);
      syncBrushToChart(nextStart, nextEnd);
    };

    const handleMouseUp = () => {
      setIsDragging(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // Real-time tick update into active candle
  useEffect(() => {
    if (activeTab !== 'kline' || !candleSeriesRef.current || trades.length === 0) return;

    const latest = trades[0];
    const nowSec = Math.floor(latest.time / 1000);
    const { intervalSec } = activeTimeframeCfg;
    const barStartSec = (Math.floor(nowSec / intervalSec) * intervalSec) as UTCTimestamp;

    const prev = currentBarRef.current;
    if (prev && prev.time === barStartSec) {
      const updatedBar = {
        time: barStartSec,
        open: prev.open,
        high: Math.max(prev.high, latest.price),
        low: Math.min(prev.low, latest.price),
        close: latest.price,
      };
      currentBarRef.current = updatedBar;
      try {
        candleSeriesRef.current.update(updatedBar);
      } catch {
        // ignore
      }
    } else {
      const newBar = {
        time: barStartSec,
        open: latest.price,
        high: latest.price,
        low: latest.price,
        close: latest.price,
      };
      currentBarRef.current = newBar;
      try {
        candleSeriesRef.current.update(newBar);
      } catch {
        // ignore
      }
    }
  }, [trades, activeTab, activeTimeframeCfg]);

  // Micro-overview sparkline for Range Brush
  const overviewSvgData = useMemo(() => {
    if (allCandles.length < 2) return null;
    const closes = allCandles.map((c) => c.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const range = max - min || 1;

    const width = 800;
    const height = 44;
    const points = closes.map((val, idx) => {
      const x = (idx / (closes.length - 1)) * width;
      const y = height - 4 - ((val - min) / range) * (height - 8);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const polyline = points.join(' ');
    const area = `0,${height} ${polyline} ${width},${height}`;
    return { width, height, polyline, area };
  }, [allCandles]);

  const startDateStr = useMemo(() => {

    if (allCandles.length === 0) return '';
    const idx = Math.min(allCandles.length - 1, Math.max(0, Math.floor((brushStart / 100) * allCandles.length)));
    const d = new Date(allCandles[idx].time * 1000);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, [allCandles, brushStart]);

  const endDateStr = useMemo(() => {
    if (allCandles.length === 0) return '';
    const idx = Math.min(allCandles.length - 1, Math.max(0, Math.ceil((brushEnd / 100) * allCandles.length) - 1));
    const d = new Date(allCandles[idx].time * 1000);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, [allCandles, brushEnd]);

  const handleApplyPresetRange = (startPct: number, endPct: number) => {
    setBrushStart(startPct);
    setBrushEnd(endPct);
    syncBrushToChart(startPct, endPct);
  };

  const handleToggleDrilldown = () => {
    if (timeframe === '1d') {
      handleSelectTimeframe('15m');
      setBrushStart(60);
      setBrushEnd(100);
      syncBrushToChart(60, 100);
    } else {
      handleSelectTimeframe('1d');
      setBrushStart(65);
      setBrushEnd(100);
      syncBrushToChart(65, 100);
    }
  };

  const visibleBarsCount = Math.round(((brushEnd - brushStart) / 100) * allCandles.length) || 45;


  return (
    <div className="chart-deck">
      <div className="chart-deck__tabs">
        {/* Left: View Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            type="button"
            className={`chart-tab-btn ${activeTab === 'kline' ? 'chart-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('kline')}
          >
            <BarChart2 size={13} style={{ display: 'inline', marginRight: 4 }} />
            专业 K 线图 ({activeTimeframeCfg.label})
          </button>
          <button
            type="button"
            className={`chart-tab-btn ${activeTab === 'depth' ? 'chart-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('depth')}
          >
            <AreaChart size={13} style={{ display: 'inline', marginRight: 4 }} />
            盘口深度山峰图 (Depth)
          </button>
        </div>

        {/* Right: Timeframe Switcher & Sampling Badge */}
        {activeTab === 'kline' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* LTTB Sampling info */}
            <span
              style={{
                fontSize: 10,
                fontFamily: 'var(--mono)',
                color: 'var(--accent)',
                background: 'hsla(190, 90%, 50%, 0.12)',
                padding: '2px 8px',
                borderRadius: 4,
                border: '1px solid hsla(190, 90%, 50%, 0.25)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
              title={locale === 'zh' ? '大屏视窗渲染点数与全局数据采样比' : 'Viewport render count and global data sampling ratio'}
            >
              <Sliders size={10} />
              {locale === 'zh' ? '视窗点数' : 'Viewport'}: {visibleBarsCount} / {allCandles.length || dataLimit} | LTTB
            </span>

            {/* Storage source badge */}
            <span
              style={{
                fontSize: 10,
                fontFamily: 'var(--mono)',
                color: dataSourceInfo === 'backend_cache' ? '#00f59b' : '#00e5ff',
                background:
                  dataSourceInfo === 'backend_cache'
                    ? 'hsla(150, 90%, 40%, 0.12)'
                    : 'hsla(190, 90%, 50%, 0.12)',
                padding: '2px 8px',
                borderRadius: 4,
                border: `1px solid ${
                  dataSourceInfo === 'backend_cache'
                    ? 'hsla(150, 90%, 40%, 0.3)'
                    : 'hsla(190, 90%, 50%, 0.3)'
                }`,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
              title={locale === 'zh' ? '后端 KlineCacheStore 持久化存储与数据同步状态' : 'Backend KlineCacheStore persistence and sync status'}
            >
              <HardDrive size={10} />
              {dataSourceInfo === 'backend_cache'
                ? (locale === 'zh' ? `后端本地存储 (${allCandles.length}根)` : `Backend Storage (${allCandles.length} bars)`)
                : dataSourceInfo === 'binance_upstream'
                ? (locale === 'zh' ? `交易所直连同步 (${allCandles.length}根)` : `Exchange Stream (${allCandles.length} bars)`)
                : (locale === 'zh' ? `后端高保真补齐 (${allCandles.length}根)` : `Synthesized (${allCandles.length} bars)`)}
            </span>

            {/* High-volume bar count selector */}
            <div className="timeframe-group" title={locale === 'zh' ? '选择后端加载的数据量档位' : 'Select cached bar count'}>
              <Database size={10} style={{ color: 'var(--muted)', marginLeft: 4, marginRight: 2 }} />
              {[300, 500, 1000, 1500].map((count) => (
                <button
                  key={count}
                  type="button"
                  className={`timeframe-btn ${dataLimit === count ? 'timeframe-btn--active' : ''}`}
                  onClick={() => setDataLimit(count)}
                  title={locale === 'zh' ? `加载 ${count} 根高密度历史 K 线` : `Load ${count} historical bars`}
                >
                  {count}{locale === 'zh' ? '根' : ' bars'}
                </button>
              ))}
            </div>

            {/* Timeframe selector */}
            <div className="timeframe-group">
              <Clock size={11} style={{ color: 'var(--muted)', marginLeft: 4, marginRight: 2 }} />
              {TIMEFRAME_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`timeframe-btn ${timeframe === opt.value ? 'timeframe-btn--active' : ''}`}
                  onClick={() => handleSelectTimeframe(opt.value)}
                  title={locale === 'zh' ? `切换至 ${opt.label}` : `Switch to ${opt.value}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Manual refresh from backend */}
            <button
              type="button"
              className="timeframe-btn"
              style={{ padding: '3px 6px', display: 'inline-flex', alignItems: 'center' }}
              onClick={() => setRefreshCount((c) => c + 1)}
              title={locale === 'zh' ? '从后端重新加载数据' : 'Reload data from backend'}
            >
              <RefreshCw size={11} className={loadingKline ? 'animate-spin' : ''} />
            </button>
          </div>
        )}

      </div>

      <div className="chart-viewport" style={{ padding: 0, position: 'relative' }}>
        {/* TAB 1: K-LINE CHART */}
        {activeTab === 'kline' && (
          <div style={{ width: '100%', position: 'relative' }}>
            <div ref={chartContainerRef} style={{ width: '100%', height: 350 }} />

            {loadingKline && (
              <div
                style={{
                  position: 'absolute',
                  top: 12,
                  right: 16,
                  fontSize: 11,
                  fontFamily: 'var(--mono)',
                  color: 'var(--accent)',
                  background: 'hsla(var(--bg-hue), 50%, 10%, 0.8)',
                  padding: '2px 8px',
                  borderRadius: 4,
                  border: '1px solid hsla(190, 90%, 50%, 0.3)',
                }}
              >
                {locale === 'zh' ? `加载 ${activeTimeframeCfg.label} K线中...` : `Loading ${timeframe} bars...`}
              </div>
            )}

            {/* DUAL-TRACK OVERVIEW-DETAIL RANGE BRUSH */}
            <div className="range-brush-container" title={locale === 'zh' ? '拖拽手柄或选区缩放主图视窗' : 'Drag handle or selection to zoom viewport'}>
              {overviewSvgData && (
                <svg
                  className="range-brush-svg"
                  viewBox={`0 0 ${overviewSvgData.width} ${overviewSvgData.height}`}
                  preserveAspectRatio="none"
                >
                  <defs>
                    <linearGradient id="brushAreaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="#00e5ff" stopOpacity="0.05" />
                    </linearGradient>
                  </defs>
                  <polygon points={overviewSvgData.area} fill="url(#brushAreaGrad)" />
                  <polyline
                    fill="none"
                    stroke="#00e5ff"
                    strokeWidth="1.2"
                    points={overviewSvgData.polyline}
                    opacity="0.8"
                  />
                </svg>
              )}

              {/* Draggable Selection Window */}
              <div
                className="range-brush-window"
                style={{
                  left: `${brushStart}%`,
                  width: `${Math.max(4, brushEnd - brushStart)}%`,
                }}
                onMouseDown={(e) => handleBrushMouseDown(e, 'window')}
              >
                {/* Left Date Tag */}
                {startDateStr && (
                  <span className="range-brush-date-tag range-brush-date-tag--left">
                    {startDateStr}
                  </span>
                )}

                {/* Left Resize Handle */}
                <div
                  className="range-brush-handle range-brush-handle--left"
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    handleBrushMouseDown(e, 'left');
                  }}
                  title={locale === 'zh' ? '向左/右拖拽调整开始时间' : 'Drag left/right to adjust start'}
                />

                {/* Right Resize Handle */}
                <div
                  className="range-brush-handle range-brush-handle--right"
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    handleBrushMouseDown(e, 'right');
                  }}
                  title={locale === 'zh' ? '向左/右拖拽调整结束时间' : 'Drag left/right to adjust end'}
                />

                {/* Right Date Tag */}
                {endDateStr && (
                  <span className="range-brush-date-tag range-brush-date-tag--right">
                    {endDateStr}
                  </span>
                )}
              </div>
            </div>

            {/* MACRO-MICRO TIME-RANGE BRUSH CONTROLS & DRILLDOWN */}
            <div className="brush-presets-bar">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--muted)', fontSize: 10 }}>{locale === 'zh' ? '宏微跨度预设:' : 'Presets:'}</span>
                <button
                  type="button"
                  className="timeframe-btn"
                  onClick={() => handleApplyPresetRange(0, 100)}
                >
                  {t.presetAll}
                </button>
                <button
                  type="button"
                  className="timeframe-btn"
                  onClick={() => handleApplyPresetRange(70, 100)}
                >
                  {t.preset3M}
                </button>
                <button
                  type="button"
                  className="timeframe-btn"
                  onClick={() => handleApplyPresetRange(90, 100)}
                >
                  {t.preset1M}
                </button>
                <button
                  type="button"
                  className="timeframe-btn"
                  onClick={() => handleApplyPresetRange(97, 100)}
                >
                  {t.preset7D}
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {startDateStr && endDateStr && (
                  <span style={{ color: 'var(--muted)', fontSize: 10 }}>
                    {locale === 'zh' ? '视窗区间:' : 'Viewport:'} <strong style={{ color: 'var(--text)' }}>{startDateStr} ~ {endDateStr}</strong> ({visibleBarsCount} {locale === 'zh' ? '根' : 'bars'})
                  </span>
                )}

                {/* Instant Drilldown to Intraday Minutes / Return to Daily Macro */}
                <button
                  type="button"
                  className={`drilldown-btn ${timeframe !== '1d' ? 'drilldown-btn--active' : ''}`}
                  onClick={handleToggleDrilldown}
                  title={timeframe === '1d' ? (locale === 'zh' ? '瞬间下钻到 15m 级别的单日分时高频蜡烛' : 'Drill down to 15m intraday bars') : (locale === 'zh' ? '返回 1D 多月全景宏观走势' : 'Return to 1D macro view')}
                >
                  <Zap size={11} />
                  {timeframe === '1d' ? `⚡ ${t.drilldownIntraday}` : `↩ ${t.returnToMacro}`}
                </button>
              </div>
            </div>
          </div>
        )}


        {/* TAB 2: DEPTH CHART */}
        {activeTab === 'depth' && (
          <div style={{ width: '100%', height: 394, padding: 12 }}>
            {orderBook.bids.length > 0 ? (
              <svg viewBox="0 0 800 340" preserveAspectRatio="none" style={{ width: '100%', height: 370 }}>
                <defs>
                  <linearGradient id="bidGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00f59b" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#00f59b" stopOpacity="0.05" />
                  </linearGradient>
                  <linearGradient id="askGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff3b69" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#ff3b69" stopOpacity="0.05" />
                  </linearGradient>
                </defs>

                {/* Center Divider */}
                <line x1="400" x2="400" y1="20" y2="300" stroke="hsl(222, 40%, 20%)" strokeDasharray="4 4" />
                
                <text
                  x="385"
                  y="325"
                  fill="var(--good)"
                  fontSize="12"
                  fontWeight="600"
                  fontFamily={SYSTEM_SANS_FONT}
                  textAnchor="end"
                >
                  {t.bidDepth} (Bids)
                </text>
                <text
                  x="415"
                  y="325"
                  fill="var(--bad)"
                  fontSize="12"
                  fontWeight="600"
                  fontFamily={SYSTEM_SANS_FONT}
                  textAnchor="start"
                >
                  {t.askDepth} (Asks)
                </text>

                {/* Bids Mountain (Left) */}
                {(() => {
                  const maxBid = orderBook.bids[orderBook.bids.length - 1]?.total || 1;
                  const pts = orderBook.bids.map((b, idx) => {
                    const x = 390 - (idx / (orderBook.bids.length - 1)) * 360;
                    const y = 300 - (b.total / maxBid) * 260;
                    return `${x.toFixed(1)},${y.toFixed(1)}`;
                  });
                  return (
                    <>
                      <polygon points={`390,300 ${pts.join(' ')} 30,300`} fill="url(#bidGrad)" />
                      <polyline fill="none" stroke="#00f59b" strokeWidth="2.5" points={`390,300 ${pts.join(' ')}`} />
                    </>
                  );
                })()}

                {/* Asks Mountain (Right) */}
                {(() => {
                  const maxAsk = orderBook.asks[orderBook.asks.length - 1]?.total || 1;
                  const pts = orderBook.asks.map((a, idx) => {
                    const x = 410 + (idx / (orderBook.asks.length - 1)) * 360;
                    const y = 300 - (a.total / maxAsk) * 260;
                    return `${x.toFixed(1)},${y.toFixed(1)}`;
                  });
                  return (
                    <>
                      <polygon points={`410,300 ${pts.join(' ')} 770,300`} fill="url(#askGrad)" />
                      <polyline fill="none" stroke="#ff3b69" strokeWidth="2.5" points={`410,300 ${pts.join(' ')}`} />
                    </>
                  );
                })()}
              </svg>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 370, color: 'var(--muted)' }}>
                等待订单簿深度数据...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
