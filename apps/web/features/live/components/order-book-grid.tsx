'use client';

import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { useI18n } from '../../../lib/i18n/context';
import type { OrderBookData } from '../../../lib/market-stream/types';

interface OrderBookGridProps {
  data: OrderBookData;
}

export function OrderBookGrid({ data }: OrderBookGridProps) {
  const { t, locale } = useI18n();
  const [copiedPrice, setCopiedPrice] = useState<number | null>(null);

  const formatPrice = (p: number) => {
    if (p >= 1000) return p.toFixed(2);
    if (p >= 1) return p.toFixed(3);
    return p.toFixed(4);
  };

  const formatAmount = (a: number) => {
    if (a >= 100) return a.toFixed(1);
    if (a >= 1) return a.toFixed(3);
    return a.toFixed(4);
  };

  const copyPrice = (price: number) => {
    try {
      navigator.clipboard.writeText(String(price));
      setCopiedPrice(price);
      setTimeout(() => setCopiedPrice(null), 1200);
    } catch {
      // ignore
    }
  };

  const reversedAsks = [...data.asks].reverse();

  return (
    <div className="dense-table-container">
      <div className="dense-table-header">
        <h3>{t.orderBook} ({data.symbol})</h3>
        <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
          {copiedPrice ? (
            <span style={{ color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
              <Check size={11} /> {t.copied} {copiedPrice}
            </span>
          ) : (
            `${data.asks.length + data.bids.length} ${locale === 'zh' ? '档深度' : 'Levels'}`
          )}
        </span>
      </div>

      <div className="dense-table-body" style={{ maxHeight: 520 }}>
        <table className="dense-table">
          <colgroup>
            <col style={{ width: '38%' }} />
            <col style={{ width: '31%' }} />
            <col style={{ width: '31%' }} />
          </colgroup>
          <thead>
            <tr>
              <th>{locale === 'zh' ? '价格 (USDT)' : 'Price (USDT)'}</th>
              <th style={{ textAlign: 'right' }}>{locale === 'zh' ? '数量' : 'Amount'}</th>
              <th style={{ textAlign: 'right' }}>{locale === 'zh' ? '累计' : 'Total'}</th>
            </tr>
          </thead>
          <tbody>
            {/* ASKS (卖盘 - 倒序展示，最低卖价贴近点差) */}
            {reversedAsks.map((ask, idx) => (
              <tr
                key={`ask-${ask.price}-${idx}`}
                className="orderbook-row"
                onClick={() => copyPrice(ask.price)}
                title={locale === 'zh' ? '点击复制价格' : 'Click to copy price'}
              >
                <td className="text-down" style={{ fontWeight: 600 }}>
                  <div
                    className="depth-bar depth-bar--ask"
                    style={{ width: `${ask.percent}%` }}
                  />
                  {formatPrice(ask.price)}
                </td>
                <td style={{ textAlign: 'right' }}>{formatAmount(ask.amount)}</td>
                <td style={{ textAlign: 'right', color: 'var(--muted)' }}>
                  {formatAmount(ask.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* 盘口点差条 SPREAD BAR */}
        <div className="orderbook-spread-bar">
          <div>
            <span style={{ color: 'var(--muted)', marginRight: 6 }}>{locale === 'zh' ? '点差 (Spread):' : 'Spread:'}</span>
            <strong style={{ color: 'var(--text)' }}>{formatPrice(data.spread)}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
              {data.spreadPct.toFixed(4)}%
            </span>
          </div>
        </div>

        {/* BIDS (买盘) */}
        <table className="dense-table">
          <colgroup>
            <col style={{ width: '38%' }} />
            <col style={{ width: '31%' }} />
            <col style={{ width: '31%' }} />
          </colgroup>
          <tbody>
            {data.bids.map((bid, idx) => (
              <tr
                key={`bid-${bid.price}-${idx}`}
                className="orderbook-row"
                onClick={() => copyPrice(bid.price)}
                title={locale === 'zh' ? '点击复制价格' : 'Click to copy price'}
              >
                <td className="text-up" style={{ fontWeight: 600 }}>
                  <div
                    className="depth-bar depth-bar--bid"
                    style={{ width: `${bid.percent}%` }}
                  />
                  {formatPrice(bid.price)}
                </td>
                <td style={{ textAlign: 'right' }}>{formatAmount(bid.amount)}</td>
                <td style={{ textAlign: 'right', color: 'var(--muted)' }}>
                  {formatAmount(bid.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
