'use client';

import React from 'react';
import { Database, Gauge, Radio, ShieldAlert } from 'lucide-react';
import { INITIAL_SYMBOLS } from '../../../lib/market-stream/stream-engine';
import type { StreamDataSource, ThrottleRate } from '../../../lib/market-stream/types';
import { useI18n } from '../../../lib/i18n/context';

interface StreamControlBarProps {
  symbol: string;
  source: StreamDataSource;
  throttle: ThrottleRate;
  whaleThreshold: number;
  onSelectSymbol: (symbol: string) => void;
  onSelectSource: (source: StreamDataSource) => void;
  onSelectThrottle: (throttle: ThrottleRate) => void;
  onUpdateWhaleThreshold: (val: number) => void;
}

export function StreamControlBar({
  symbol,
  source,
  throttle,
  whaleThreshold,
  onSelectSymbol,
  onSelectSource,
  onSelectThrottle,
  onUpdateWhaleThreshold,
}: StreamControlBarProps) {
  const { t, locale } = useI18n();

  return (
    <div className="live-controls">
      <div className="live-controls__group">
        {/* SYMBOL SELECT */}
        <label className="live-controls__field">
          <Database size={13} style={{ color: 'var(--accent)' }} />
          <span>{t.activeSymbol}:</span>
          <select value={symbol} onChange={(e) => onSelectSymbol(e.target.value)}>
            {INITIAL_SYMBOLS.map((s) => (
              <option key={s.symbol} value={s.symbol}>
                {s.name} ({s.symbol})
              </option>
            ))}
          </select>
        </label>

        {/* DATA SOURCE */}
        <label className="live-controls__field">
          <Radio size={13} style={{ color: source === 'simulator' ? '#ffb800' : 'var(--good)' }} />
          <span>{t.dataSource}:</span>
          <select
            value={source}
            onChange={(e) => onSelectSource(e.target.value as StreamDataSource)}
            style={{
              borderColor: source === 'simulator' ? '#ffb800' : 'var(--line)',
              color: source === 'simulator' ? '#ffb800' : 'var(--text)',
            }}
          >
            <option value="binance">Binance Public WebSocket {locale === 'zh' ? '(免鉴权)' : '(Public)'}</option>
            <option value="okx">OKX Public WebSocket {locale === 'zh' ? '(免鉴权)' : '(Public)'}</option>
            <option value="simulator">{locale === 'zh' ? '⚡ 高频压测模拟引擎 (200 TPS)' : '⚡ High-Freq Stress Engine (200 TPS)'}</option>
          </select>
        </label>
      </div>

      <div className="live-controls__group">
        {/* THROTTLE / FPS */}
        <label className="live-controls__field">
          <Gauge size={13} style={{ color: 'var(--accent)' }} />
          <span>{t.throttleRate}:</span>
          <select
            value={throttle}
            onChange={(e) => onSelectThrottle(e.target.value as ThrottleRate)}
          >
            <option value="realtime">{locale === 'zh' ? '实时无节流 (原生高吞吐)' : 'Realtime (Max Throughput)'}</option>
            <option value="100ms">{locale === 'zh' ? '100ms 批量渲染 (均衡)' : '100ms Batch (Balanced)'}</option>
            <option value="250ms">{locale === 'zh' ? '250ms 批量渲染 (节能)' : '250ms Batch (Power Saving)'}</option>
            <option value="500ms">{locale === 'zh' ? '500ms 批量渲染 (极简)' : '500ms Batch (Minimal)'}</option>
          </select>
        </label>

        {/* WHALE ALERT THRESHOLD */}
        <label className="live-controls__field">
          <ShieldAlert size={13} style={{ color: '#ffb800' }} />
          <span>{t.whaleThresholdLabel}:</span>
          <input
            type="number"
            min={500}
            max={500000}
            step={500}
            value={whaleThreshold}
            onChange={(e) => onUpdateWhaleThreshold(Number(e.target.value) || 5000)}
            style={{ width: 85 }}
          />
        </label>
      </div>
    </div>
  );
}
