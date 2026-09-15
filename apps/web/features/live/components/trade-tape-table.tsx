'use client';

import React, { useMemo, useRef, useState } from 'react';
import { BarChart3, DollarSign, Filter, Pause, SlidersHorizontal, Zap } from 'lucide-react';
import { useI18n } from '../../../lib/i18n/context';
import type { TradeItem } from '../../../lib/market-stream/types';

interface TradeTapeTableProps {
  trades: TradeItem[];
  whaleThreshold: number;
}

type SideFilter = 'all' | 'buy' | 'sell';

interface AmountBucket {
  id: string;
  label: string;
  min: number;
  max: number;
  subLabelZh: string;
  subLabelEn: string;
}

const HISTOGRAM_BUCKETS: AmountBucket[] = [
  { id: 'micro', label: '< $1K', min: 0, max: 1000, subLabelZh: '散户单', subLabelEn: 'Retail' },
  { id: 'standard', label: '$1K - $5K', min: 1000, max: 5000, subLabelZh: '标准单', subLabelEn: 'Standard' },
  { id: 'large', label: '$5K - $20K', min: 5000, max: 20000, subLabelZh: '大单', subLabelEn: 'Large' },
  { id: 'xlarge', label: '$20K - $50K', min: 20000, max: 50000, subLabelZh: '机构单', subLabelEn: 'Institutional' },
  { id: 'whale', label: '≥ $50K', min: 50000, max: Infinity, subLabelZh: '🐋 巨鲸单', subLabelEn: '🐋 Whale' },
];

const ROW_HEIGHT = 34;
const VISIBLE_HEIGHT = 320;
const OVERSCAN = 5;

export function TradeTapeTable({ trades, whaleThreshold }: TradeTapeTableProps) {
  const { t, locale } = useI18n();
  const [sideFilter, setSideFilter] = useState<SideFilter>('all');
  const [minAmountFilter, setMinAmountFilter] = useState(0);
  const [selectedBucketId, setSelectedBucketId] = useState<string | null>(null);
  const [showFilterBar, setShowFilterBar] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [frozenTrades, setFrozenTrades] = useState<TradeItem[]>([]);
  const [scrollTop, setScrollTop] = useState(0);

  const containerRef = useRef<HTMLDivElement | null>(null);

  const handleMouseEnter = () => {
    setIsPaused(true);
    setFrozenTrades(trades);
  };

  const handleMouseLeave = () => {
    setIsPaused(false);
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  const displayTrades = isPaused ? frozenTrades : trades;

  // Calculate real-time histogram bucket counts & buy/sell breakdown
  const histogramMetrics = useMemo(() => {
    const counts: Record<string, { total: number; buy: number; sell: number }> = {};
    for (const b of HISTOGRAM_BUCKETS) {
      counts[b.id] = { total: 0, buy: 0, sell: 0 };
    }

    for (const t of displayTrades) {
      for (const b of HISTOGRAM_BUCKETS) {
        if (t.total >= b.min && t.total < b.max) {
          counts[b.id].total++;
          if (t.side === 'buy') counts[b.id].buy++;
          else counts[b.id].sell++;
          break;
        }
      }
    }

    const maxCount = Math.max(1, ...Object.values(counts).map((c) => c.total));
    return { counts, maxCount };
  }, [displayTrades]);

  // Faceted + Histogram Filtering
  const filteredTrades = useMemo(() => {
    return displayTrades.filter((t) => {
      if (sideFilter === 'buy' && t.side !== 'buy') return false;
      if (sideFilter === 'sell' && t.side !== 'sell') return false;
      if (minAmountFilter > 0 && t.total < minAmountFilter) return false;
      if (selectedBucketId) {
        const bucket = HISTOGRAM_BUCKETS.find((b) => b.id === selectedBucketId);
        if (bucket && (t.total < bucket.min || t.total >= bucket.max)) {
          return false;
        }
      }
      return true;
    });
  }, [displayTrades, sideFilter, minAmountFilter, selectedBucketId]);


  // Virtual Window Calculation
  const totalCount = filteredTrades.length;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(
    totalCount,
    Math.ceil((scrollTop + VISIBLE_HEIGHT) / ROW_HEIGHT) + OVERSCAN,
  );

  const visibleItems = filteredTrades.slice(startIndex, endIndex);
  const topPadding = startIndex * ROW_HEIGHT;
  const bottomPadding = Math.max(0, (totalCount - endIndex) * ROW_HEIGHT);

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    const s = String(d.getSeconds()).padStart(2, '0');
    const ms = String(d.getMilliseconds()).padStart(3, '0');
    return `${h}:${m}:${s}.${ms}`;
  };

  const formatPrice = (p: number) => {
    if (p >= 1000) return p.toFixed(2);
    if (p >= 1) return p.toFixed(3);
    return p.toFixed(4);
  };

  const formatAmount = (a: number) => {
    if (a >= 10) return a.toFixed(2);
    if (a >= 1) return a.toFixed(3);
    return a.toFixed(4);
  };

  const formatTotal = (tot: number) => {
    return tot.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  };

  return (
    <div className="dense-table-container">
      <div className="dense-table-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h3>
            <Zap size={14} style={{ color: 'var(--accent)' }} />
            实时逐笔成交流水
          </h3>
          <span
            style={{
              fontSize: 10,
              fontFamily: 'var(--mono)',
              background: 'hsla(var(--bg-hue), 40%, 20%, 0.8)',
              padding: '1px 6px',
              borderRadius: 4,
              color: 'var(--muted)',
            }}
          >
            内存 {trades.length} / 视窗虚拟渲染 {visibleItems.length}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isPaused && (
            <span
              style={{
                fontSize: 10,
                color: '#ffb800',
                background: 'rgba(255, 184, 0, 0.15)',
                padding: '2px 6px',
                borderRadius: 4,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontWeight: 600,
              }}
            >
              <Pause size={10} /> 悬停已暂停
            </span>
          )}

          <button
            type="button"
            className={`icon-button ${showFilterBar ? 'icon-button--active' : ''}`}
            onClick={() => setShowFilterBar(!showFilterBar)}
            style={{
              padding: '3px 8px',
              fontSize: 11,
              height: 24,
              background: showFilterBar ? 'hsla(190, 90%, 50%, 0.15)' : 'var(--panel)',
              color: showFilterBar ? 'var(--accent)' : 'var(--muted)',
              borderColor: showFilterBar ? 'var(--accent)' : 'var(--line)',
            }}
          >
            <SlidersHorizontal size={11} />
            <span>列级分箱过滤</span>
          </button>
        </div>
      </div>

      {/* FACET RANGE & HISTOGRAM FILTER BAR */}
      {showFilterBar && (
        <>
          {/* 1. COLUMN-LEVEL TRADE AMOUNT DISTRIBUTION HISTOGRAM */}
          <div className="histogram-filter-bar">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--muted)' }}>
                <BarChart3 size={12} style={{ color: 'var(--accent)' }} />
                <span style={{ fontWeight: 600, color: 'var(--text)' }}>{locale === 'zh' ? '列级成交额分布直方图' : 'Column Volume Histogram'}</span>
                <span>{locale === 'zh' ? '(点击柱子瞬间过滤)' : '(Click bar to filter)'}</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {selectedBucketId && (
                  <button
                    type="button"
                    className="filter-pill"
                    onClick={() => setSelectedBucketId(null)}
                    style={{ fontSize: 9, padding: '1px 6px', color: '#00e5ff', borderColor: '#00e5ff' }}
                  >
                    {locale === 'zh' ? '清除直方图过滤' : 'Clear histogram filter'}
                  </button>
                )}
                <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                  {locale === 'zh' ? '匹配:' : 'Matches:'} <strong style={{ color: '#00e5ff' }}>{filteredTrades.length}</strong> / {displayTrades.length} {locale === 'zh' ? '笔' : 'trades'}
                </span>
              </div>
            </div>

            {/* 5 Column Histogram Bars */}
            <div className="histogram-track-container">
              {HISTOGRAM_BUCKETS.map((bucket) => {
                const data = histogramMetrics.counts[bucket.id] || { total: 0, buy: 0, sell: 0 };
                const isSelected = selectedBucketId === bucket.id;
                const barHeightPct = Math.max(12, Math.round((data.total / histogramMetrics.maxCount) * 100));
                const buyRatio = data.total > 0 ? (data.buy / data.total) * 100 : 50;
                const sellRatio = data.total > 0 ? (data.sell / data.total) * 100 : 50;
                const subLabel = locale === 'zh' ? bucket.subLabelZh : bucket.subLabelEn;

                return (
                  <div
                    key={bucket.id}
                    className={`histogram-bucket-column ${isSelected ? 'histogram-bucket-column--active' : ''}`}
                    onClick={() => setSelectedBucketId(isSelected ? null : bucket.id)}
                    title={locale === 'zh'
                      ? `点击${isSelected ? '取消' : '仅查看'} ${bucket.label}（${subLabel}）共 ${data.total} 笔（买盘 ${data.buy} / 卖盘 ${data.sell}）`
                      : `Click to ${isSelected ? 'clear' : 'filter'} ${bucket.label} (${subLabel}) total ${data.total} (Buy ${data.buy} / Sell ${data.sell})`}
                  >
                    <div className="histogram-count">{data.total}{locale === 'zh' ? '笔' : ''}</div>

                    {/* Stacked Buy/Sell bar */}
                    <div className="histogram-bar-stack" style={{ height: `${barHeightPct}%`, maxHeight: 28 }}>
                      <div className="histogram-bar-sell" style={{ height: `${sellRatio}%` }} />
                      <div className="histogram-bar-buy" style={{ height: `${buyRatio}%` }} />
                    </div>

                    <div className="histogram-label">{bucket.label}</div>
                    <div className="histogram-sublabel">{subLabel}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 2. DIRECTION & MIN AMOUNT FILTER */}
          <div className="facet-filter-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--muted)', fontSize: 10 }}>{locale === 'zh' ? '方向:' : 'Side:'}</span>
              <button
                type="button"
                className={`filter-pill ${sideFilter === 'all' ? 'filter-pill--active' : ''}`}
                onClick={() => setSideFilter('all')}
              >
                {t.historyAll}
              </button>
              <button
                type="button"
                className={`filter-pill ${sideFilter === 'buy' ? 'filter-pill--active' : ''}`}
                onClick={() => setSideFilter('buy')}
              >
                {locale === 'zh' ? '🟢 买盘' : '🟢 Buy'}
              </button>
              <button
                type="button"
                className={`filter-pill ${sideFilter === 'sell' ? 'filter-pill--active' : ''}`}
                onClick={() => setSideFilter('sell')}
              >
                {locale === 'zh' ? '🔴 卖盘' : '🔴 Sell'}
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
              <span style={{ color: 'var(--muted)', fontSize: 10 }}>
                {locale === 'zh' ? '最小成交额:' : 'Min Amount:'} ${minAmountFilter.toLocaleString()}
              </span>
              <input
                type="range"
                min={0}
                max={25000}
                step={1000}
                value={minAmountFilter}
                onChange={(e) => setMinAmountFilter(Number(e.target.value))}
                style={{ width: 90, height: 4, accentColor: 'var(--accent)', cursor: 'pointer' }}
              />
              {minAmountFilter > 0 && (
                <button
                  type="button"
                  className="filter-pill"
                  onClick={() => setMinAmountFilter(0)}
                  style={{ fontSize: 9, padding: '1px 5px' }}
                >
                  {locale === 'zh' ? '重置' : 'Reset'}
                </button>
              )}
            </div>
          </div>
        </>
      )}

      <div
        ref={containerRef}
        className="dense-table-body"
        style={{ maxHeight: VISIBLE_HEIGHT, position: 'relative' }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onScroll={handleScroll}
      >
        <table className="dense-table">
          <colgroup>
            <col style={{ width: '22%' }} />
            <col style={{ width: '15%' }} />
            <col style={{ width: '22%' }} />
            <col style={{ width: '18%' }} />
            <col style={{ width: '23%' }} />
          </colgroup>
          <thead>
            <tr>
              <th>{locale === 'zh' ? '时间 (毫秒)' : 'Time (ms)'}</th>
              <th>{locale === 'zh' ? '方向' : 'Side'}</th>
              <th style={{ textAlign: 'right' }}>{locale === 'zh' ? '成交价 (USDT)' : 'Price (USDT)'}</th>
              <th style={{ textAlign: 'right' }}>{locale === 'zh' ? '数量' : 'Amount'}</th>
              <th style={{ textAlign: 'right' }}>{locale === 'zh' ? '成交额 (USDT)' : 'Total (USDT)'}</th>
            </tr>
          </thead>
          <tbody>
            {/* VIRTUAL TOP SPACER */}
            {topPadding > 0 && (
              <tr style={{ height: topPadding, border: 0 }}>
                <td colSpan={5} style={{ padding: 0, border: 0 }} />
              </tr>
            )}

            {visibleItems.map((t) => {
              const isBuy = t.side === 'buy';
              return (
                <tr
                  key={t.id}
                  className={`trade-row ${t.isWhale ? 'trade-row--whale' : ''}`}
                  style={{ height: ROW_HEIGHT }}
                >
                  <td style={{ color: 'var(--muted)' }}>{formatTime(t.time)}</td>
                  <td>
                    <span className={isBuy ? 'badge-up' : 'badge-down'}>
                      {isBuy ? 'BUY' : 'SELL'}
                    </span>
                  </td>
                  <td
                    className={isBuy ? 'text-up' : 'text-down'}
                    style={{ textAlign: 'right', fontWeight: 600 }}
                  >
                    {formatPrice(t.price)}
                  </td>
                  <td style={{ textAlign: 'right' }}>{formatAmount(t.amount)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 500 }}>
                    {t.isWhale && (
                      <span className="whale-pill" style={{ marginRight: 4 }}>
                        🐋
                      </span>
                    )}
                    ${formatTotal(t.total)}
                  </td>
                </tr>
              );
            })}

            {/* VIRTUAL BOTTOM SPACER */}
            {bottomPadding > 0 && (
              <tr style={{ height: bottomPadding, border: 0 }}>
                <td colSpan={5} style={{ padding: 0, border: 0 }} />
              </tr>
            )}

            {filteredTrades.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)', padding: 25 }}>
                  {locale === 'zh' ? '没有符合当前过滤条件的成交记录' : 'No trades match the current filter'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
