'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Cpu, HardDrive, Keyboard, Radio, Wifi, Zap } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { useI18n } from '../../lib/i18n/context';
import { useMarketStream } from '../../lib/market-stream/use-market-stream';
import { StreamControlBar } from './components/stream-control-bar';
import { TickerMatrixTable } from './components/ticker-matrix-table';
import { OrderBookGrid } from './components/order-book-grid';
import { TradeTapeTable } from './components/trade-tape-table';
import { LiveChartsDeck, type Timeframe } from './components/live-charts-deck';
import { RuntimeEngineHud } from './components/runtime-engine-hud';


export function LiveStreamWorkbench() {
  const { t, locale } = useI18n();
  const {
    symbol,
    source,
    throttle,
    whaleThreshold,
    tickers,
    orderBook,
    trades,
    metrics,
    selectSymbol,
    selectSource,
    selectThrottle,
    updateWhaleThreshold,
  } = useMarketStream('BTCUSDT');

  const [timeframe, setTimeframe] = useState<Timeframe>('1d');

  // Keyboard shortcut listener: 1~6 for timeframes, Space for pause/resume
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      if (e.key === '1') setTimeframe('1m');
      else if (e.key === '2') setTimeframe('15m');
      else if (e.key === '3') setTimeframe('30m');
      else if (e.key === '4') setTimeframe('1h');
      else if (e.key === '5') setTimeframe('4h');
      else if (e.key === '6') setTimeframe('1d');
      else if (e.key === ' ') {
        e.preventDefault();
        selectThrottle(throttle === 'realtime' ? '500ms' : 'realtime');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [throttle, selectThrottle]);

  const activeTicker = useMemo(() => {
    return tickers.find((t) => t.symbol === symbol) ?? tickers[0];
  }, [tickers, symbol]);

  const latestPrice = activeTicker?.price || 68400;

  return (
    <AppShell title={t.navLive}>
      <div className="live-workspace">
        {/* TOP HUD SYSTEM MONITOR - LARGE & MAJESTIC */}
        <div className="live-hud">
          {/* Card 1: Connection & Source */}
          <div className={`hud-card ${metrics.status === 'connected' ? 'hud-card--connected' : 'hud-card--connecting'}`}>
            <div className="hud-card__head">
              <span className="hud-card__label">{locale === 'zh' ? '连接引擎 / 数据源' : 'Engine / Data Source'}</span>
              <div className="hud-card__icon-box">
                <Radio size={16} style={{ color: metrics.status === 'connected' ? 'var(--good)' : 'var(--warn)' }} />
              </div>
            </div>
            <div className="hud-card__value">
              <span>
                {source === 'binance' ? 'Binance WS' : source === 'okx' ? 'OKX WS' : (locale === 'zh' ? '高频模拟压测' : 'Stress Simulator')}
              </span>
            </div>
            <div className="hud-card__sub">
              <span className="radar-dot" style={{ width: 6, height: 6 }} />
              <span style={{ color: metrics.status === 'connected' ? 'var(--good)' : 'var(--warn)', fontWeight: 600 }}>
                {metrics.status === 'connected'
                  ? (locale === 'zh' ? '已稳定连通 (零鉴权)' : 'Connected (No Auth)')
                  : (locale === 'zh' ? '正在连接链路...' : 'Connecting...')}
              </span>
            </div>
          </div>

          {/* Card 2: TPS / Throughput */}
          <div className="hud-card hud-card--accent">
            <div className="hud-card__head">
              <span className="hud-card__label">{locale === 'zh' ? '实时吞吐量 (Throughput)' : 'Throughput (TPS)'}</span>
              <div className="hud-card__icon-box">
                <Activity size={16} style={{ color: 'var(--accent)' }} />
              </div>
            </div>
            <div className="hud-card__value" style={{ color: 'var(--accent)' }}>
              {metrics.tps}
              <span className="hud-card__unit">ticks / s</span>
            </div>
            <div className="hud-card__sub">
              <span>{locale === 'zh' ? '采样周期 1,000ms 平滑滑动均值' : '1,000ms rolling average'}</span>
            </div>
          </div>

          {/* Card 3: Network Latency */}
          <div className="hud-card">
            <div className="hud-card__head">
              <span className="hud-card__label">{locale === 'zh' ? '链路延迟 (Latency)' : 'Network Latency'}</span>
              <div className="hud-card__icon-box">
                <Wifi size={16} style={{ color: metrics.latencyMs < 50 ? 'var(--good)' : 'var(--warn)' }} />
              </div>
            </div>
            <div className="hud-card__value">
              {metrics.latencyMs}
              <span className="hud-card__unit">ms</span>
            </div>
            <div className="hud-card__sub">
              <span style={{ color: 'var(--good)' }}>{locale === 'zh' ? '● 往返延迟极佳' : '● Excellent RTT'}</span>
            </div>
          </div>

          {/* Card 4: Total Packets */}
          <div className="hud-card">
            <div className="hud-card__head">
              <span className="hud-card__label">{locale === 'zh' ? '已摄入总数据包' : 'Ingested Frames'}</span>
              <div className="hud-card__icon-box">
                <Cpu size={16} style={{ color: 'var(--accent)' }} />
              </div>
            </div>
            <div className="hud-card__value">
              {metrics.totalMessages.toLocaleString()}
              <span className="hud-card__unit">frames</span>
            </div>
            <div className="hud-card__sub">
              <span>{locale === 'zh' ? '零丢帧流水线处理' : 'Zero-drop pipeline'}</span>
            </div>
          </div>

          {/* Card 5: Memory Buffer */}
          <div className="hud-card">
            <div className="hud-card__head">
              <span className="hud-card__label">{locale === 'zh' ? '流式环形缓冲' : 'Ring Buffer'}</span>
              <div className="hud-card__icon-box">
                <HardDrive size={16} style={{ color: 'var(--muted)' }} />
              </div>
            </div>
            <div className="hud-card__value">
              {metrics.bufferKb}
              <span className="hud-card__unit">KB</span>
            </div>
            <div className="hud-card__sub">
              <span>{locale === 'zh' ? '自动垃圾回收机制正常' : 'Auto GC nominal'}</span>
            </div>
          </div>
        </div>

        {/* CONTROL DECK */}
        <StreamControlBar
          symbol={symbol}
          source={source}
          throttle={throttle}
          whaleThreshold={whaleThreshold}
          onSelectSymbol={selectSymbol}
          onSelectSource={selectSource}
          onSelectThrottle={selectThrottle}
          onUpdateWhaleThreshold={updateWhaleThreshold}
        />

        {/* 3-COLUMN HIGH-DENSITY WORKSPACE GRID */}
        <div className="live-layout-grid">
          {/* LEFT: Multi-Ticker Matrix */}
          <section>
            <TickerMatrixTable
              tickers={tickers}
              selectedSymbol={symbol}
              onSelectSymbol={selectSymbol}
            />
          </section>

          {/* CENTER: Charts Deck + Trade Blotter */}
          <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <LiveChartsDeck
              symbol={symbol}
              trades={trades}
              orderBook={orderBook}
              latestPrice={latestPrice}
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
            />
            <TradeTapeTable
              trades={trades}
              whaleThreshold={whaleThreshold}
            />
          </section>

          {/* RIGHT: L2 Order Book */}
          <section>
            <OrderBookGrid data={orderBook} />
          </section>
        </div>

        {/* FOOTER: PRO TRADER HOTKEY BAR */}
        <div className="hotkey-bar">
          <div className="hotkey-group">
            <div className="hotkey-item">
              <Keyboard size={13} style={{ color: 'var(--accent)' }} />
              <span style={{ fontWeight: 600, color: 'var(--text)' }}>{t.geekHotkeys}:</span>
            </div>
            <div className="hotkey-item">
              <span className="hotkey-kbd">1 - 6</span>
              <span>{t.hotkeyTimeframe}</span>
            </div>
            <div className="hotkey-item">
              <span className="hotkey-kbd">{t.spaceKey}</span>
              <span>{t.hotkeyPauseResume}</span>
            </div>
            <div className="hotkey-item">
              <span className="hotkey-kbd">{t.dragTimeline}</span>
              <span>{t.hotkeyTimeBrush}</span>
            </div>
            <div className="hotkey-item">
              <span className="hotkey-kbd">{t.clickOrderPrice}</span>
              <span>{t.hotkeyCopyPrice}</span>
            </div>
          </div>
          <div style={{ color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--mono)', fontSize: 10 }}>
            ⚡ PRO TRADER WORKSTATION
          </div>
        </div>

        {/* FLOATING RUNTIME ENGINE HUD */}
        <RuntimeEngineHud />
      </div>
    </AppShell>

  );
}
