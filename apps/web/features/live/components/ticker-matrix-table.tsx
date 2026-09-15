'use client';

import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import type { TickerItem } from '../../../lib/market-stream/types';
import { useI18n } from '../../../lib/i18n/context';

type SortKey = 'symbol' | 'price' | 'change24hPct' | 'volume24h';

interface TickerMatrixTableProps {
  tickers: TickerItem[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
}

function MiniSparkline({ data, isPositive }: { data: number[]; isPositive: boolean }) {
  if (!data || data.length < 2) return <div style={{ width: 48, height: 18 }} />;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 48;
  const height = 18;
  const pad = 2;

  const points = data.map((val, idx) => {
    const x = (idx / (data.length - 1)) * (width - pad * 2) + pad;
    const y = height - pad - ((val - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const color = isPositive ? '#00f59b' : '#ff3b69';

  return (
    <svg width={width} height={height} style={{ display: 'block', margin: '0 auto' }}>
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points.join(' ')}
      />
    </svg>
  );
}

export function TickerMatrixTable({
  tickers,
  selectedSymbol,
  onSelectSymbol,
}: TickerMatrixTableProps) {
  const { t } = useI18n();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('volume24h');
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const filteredTickers = useMemo(() => {
    let result = tickers;
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      result = result.filter(
        (t) => t.symbol.toUpperCase().includes(q) || t.name.toUpperCase().includes(q),
      );
    }

    return [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'symbol') cmp = a.symbol.localeCompare(b.symbol);
      else if (sortKey === 'price') cmp = a.price - b.price;
      else if (sortKey === 'change24hPct') cmp = a.change24hPct - b.change24hPct;
      else if (sortKey === 'volume24h') cmp = a.volume24h - b.volume24h;
      return sortAsc ? cmp : -cmp;
    });
  }, [tickers, search, sortKey, sortAsc]);

  const formatPrice = (p: number) => {
    if (p >= 1000) return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (p >= 1) return p.toFixed(3);
    return p.toFixed(4);
  };

  const formatVolume = (v: number) => {
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
    return v.toFixed(0);
  };

  const formatMicroPrice = (p: number) => {
    if (p >= 1000) return Math.round(p).toString();
    if (p >= 1) return p.toFixed(2);
    return p.toFixed(3);
  };

  return (
    <div className="dense-table-container">
      <div className="dense-table-header">
        <h3>{t.tickerMatrix} ({filteredTickers.length})</h3>
        <div style={{ position: 'relative', width: 130 }}>
          <Search
            size={12}
            style={{ position: 'absolute', left: 6, top: 7, color: 'var(--muted)' }}
          />
          <input
            type="text"
            placeholder={t.searchSymbol}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              paddingLeft: 22,
              paddingRight: 6,
              paddingTop: 3,
              paddingBottom: 3,
              fontSize: 11,
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text)',
            }}
          />
        </div>
      </div>

      <div className="dense-table-body">
        <table className="dense-table">
          <colgroup>
            <col style={{ width: '27%' }} />
            <col style={{ width: '24%' }} />
            <col style={{ width: '18%' }} />
            <col style={{ width: '15%' }} />
            <col style={{ width: '16%' }} />
          </colgroup>
          <thead>
            <tr>
              <th onClick={() => handleSort('symbol')} style={{ cursor: 'pointer' }}>
                {t.symbolColumn} {sortKey === 'symbol' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th onClick={() => handleSort('price')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                {t.priceRangeColumn} {sortKey === 'price' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th onClick={() => handleSort('change24hPct')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                {t.change24hColumn} {sortKey === 'change24hPct' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th style={{ textAlign: 'center' }}>{t.trendColumn}</th>
              <th onClick={() => handleSort('volume24h')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                {t.volumeColumn} {sortKey === 'volume24h' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredTickers.map((tItem) => {
              const isSelected = tItem.symbol === selectedSymbol;
              const isPos = tItem.change24hPct >= 0;
              const flashClass =
                tItem.direction === 'up'
                  ? 'tick-flash-up'
                  : tItem.direction === 'down'
                    ? 'tick-flash-down'
                    : '';

              const range = Math.max(tItem.high24h - tItem.low24h, 0.0001);
              const posRatio = Math.max(0, Math.min(1, (tItem.price - tItem.low24h) / range));
              const posPct = Math.round(posRatio * 100);

              return (
                <tr
                  key={tItem.symbol}
                  className={`ticker-row ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelectSymbol(tItem.symbol)}
                  title={`${t.clickToSwitch} ${tItem.symbol}`}
                >
                  <td>
                    <span className="ticker-symbol">{tItem.symbol}</span>
                    <span className="ticker-name">{tItem.name}</span>
                  </td>
                  <td className={flashClass} style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{formatPrice(tItem.price)}</div>
                    {/* In-cell 24h High/Low Position Bar */}
                    <div className="in-cell-meter">
                      <div className="meter-track">
                        <div className="meter-fill" style={{ width: `${posPct}%` }} />
                      </div>
                      <div className="meter-labels">
                        <span>L:{formatMicroPrice(tItem.low24h)}</span>
                        <span>H:{formatMicroPrice(tItem.high24h)}</span>
                      </div>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <span className={isPos ? 'badge-up' : 'badge-down'}>
                      {isPos ? '+' : ''}
                      {tItem.change24hPct.toFixed(2)}%
                    </span>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <MiniSparkline data={tItem.sparkline} isPositive={isPos} />
                  </td>
                  <td style={{ textAlign: 'right', color: 'var(--muted)', fontSize: 11 }}>
                    {formatVolume(tItem.volume24h)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
