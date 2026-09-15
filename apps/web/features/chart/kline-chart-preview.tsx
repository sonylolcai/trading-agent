'use client';

import React, { useState } from 'react';
import { toChartCandles, type ChartCandle } from '../../lib/chart';
import type { KlineFramePayload } from '../../types/api';
import { useI18n } from '../../lib/i18n/context';

type KlineChartPreviewProps = {
  frame?: KlineFramePayload;
};

export function KlineChartPreview({ frame }: KlineChartPreviewProps) {
  const { t } = useI18n();
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!frame || frame.bars.length === 0) {
    return <div className="empty-state">{t.noCachedKline}</div>;
  }

  const candles = toChartCandles(frame).slice(-80);
  const highs = candles.map((bar) => bar.high);
  const lows = candles.map((bar) => bar.low);
  const volumes = candles.map((bar) => bar.volume);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const maxVol = Math.max(...volumes, 1);
  const spread = Math.max(max - min, 0.0001);

  const width = Math.max(candles.length * 10, 480);
  const totalHeight = 280;
  const candleHeight = 200;
  const volHeight = 60;
  const padX = 16;
  const padTop = 16;

  const xStep = (width - padX * 2) / Math.max(candles.length - 1, 1);
  const yPrice = (price: number) => padTop + ((max - price) / spread) * (candleHeight - padTop);
  const yVol = (vol: number) => totalHeight - 8 - (vol / maxVol) * (volHeight - 12);

  // Highest and Lowest index
  const highIndex = highs.indexOf(max);
  const lowIndex = lows.indexOf(min);
  const latestCandle = candles[candles.length - 1];
  const activeCandle = hoverIndex !== null && candles[hoverIndex] ? candles[hoverIndex] : latestCandle;
  const activeChangePct = activeCandle ? ((activeCandle.close - activeCandle.open) / (activeCandle.open || 1)) * 100 : 0;

  const formatPrice = (p: number) => (p >= 100 ? p.toFixed(2) : p >= 1 ? p.toFixed(3) : p.toFixed(4));
  const formatVol = (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}K` : String(v));

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const relX = (clientX / rect.width) * width;
    const idx = Math.round((relX - padX) / xStep);
    const clamped = Math.max(0, Math.min(candles.length - 1, idx));
    setHoverIndex(clamped);
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
  };

  return (
    <div className="chart-preview chart-preview--enhanced" aria-label={`${frame.symbol} ${frame.timeframe} candle preview`}>
      {/* Top Interactive OHLC HUD Bar */}
      <div className="chart-preview__hud">
        <div className="chart-preview__hud-meta">
          <span className="chart-preview__hud-symbol">{frame.symbol}</span>
          <span className="chart-preview__hud-timeframe">{frame.timeframe}</span>
        </div>
        {activeCandle && (
          <div className="chart-preview__hud-stats">
            <span className="hud-label">O: <strong className="hud-val">{formatPrice(activeCandle.open)}</strong></span>
            <span className="hud-label">H: <strong className="hud-val hud-val--high">{formatPrice(activeCandle.high)}</strong></span>
            <span className="hud-label">L: <strong className="hud-val hud-val--low">{formatPrice(activeCandle.low)}</strong></span>
            <span className="hud-label">C: <strong className={`hud-val ${activeChangePct >= 0 ? 'text-good' : 'text-bad'}`}>{formatPrice(activeCandle.close)}</strong></span>
            <span className="hud-label">V: <strong className="hud-val">{formatVol(activeCandle.volume)}</strong></span>
            <span className={`hud-badge ${activeChangePct >= 0 ? 'hud-badge--up' : 'hud-badge--down'}`}>
              {activeChangePct >= 0 ? '+' : ''}{activeChangePct.toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      <div className="chart-preview__canvas-wrap">
        <svg
          viewBox={`0 0 ${width} ${totalHeight}`}
          role="img"
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Horizontal Gridlines */}
          <line className="chart-preview__grid" x1={padX} x2={width - padX} y1={yPrice(max)} y2={yPrice(max)} />
          <line className="chart-preview__grid" x1={padX} x2={width - padX} y1={yPrice((max + min) / 2)} y2={yPrice((max + min) / 2)} strokeDasharray="3 3" />
          <line className="chart-preview__grid" x1={padX} x2={width - padX} y1={yPrice(min)} y2={yPrice(min)} />
          <line className="chart-preview__grid chart-preview__grid--sub" x1={padX} x2={width - padX} y1={candleHeight + 4} y2={candleHeight + 4} />

          {/* Volume Separator Text */}
          <text x={padX + 2} y={candleHeight + 14} className="chart-preview__label">VOL (MAX: {formatVol(maxVol)})</text>

          {/* Candles & Volume Bars */}
          {candles.map((bar, index) => {
            const x = padX + index * xStep;
            const up = bar.close >= bar.open;
            const bodyTop = yPrice(Math.max(bar.open, bar.close));
            const bodyBottom = yPrice(Math.min(bar.open, bar.close));
            const bodyHeight = Math.max(bodyBottom - bodyTop, 2);
            const vY = yVol(bar.volume);
            const vH = Math.max(totalHeight - 8 - vY, 1);

            return (
              <g key={`${bar.seq}-${bar.time}`} className={up ? 'candle candle--up' : 'candle candle--down'}>
                {/* Wick */}
                <line x1={x} x2={x} y1={yPrice(bar.high)} y2={yPrice(bar.low)} strokeWidth={1} />
                {/* Body */}
                <rect x={x - 3} y={bodyTop} width={6} height={bodyHeight} rx={1} />
                {/* Volume Bar */}
                <rect
                  x={x - 2.5}
                  y={vY}
                  width={5}
                  height={vH}
                  className={`vol-bar ${up ? 'vol-bar--up' : 'vol-bar--down'}`}
                  opacity={0.65}
                />
              </g>
            );
          })}

          {/* High Price Marker */}
          {highIndex >= 0 && (
            <g className="chart-marker chart-marker--high">
              <circle cx={padX + highIndex * xStep} cy={yPrice(max)} r={2.5} fill="var(--good)" />
              <text
                x={Math.min(padX + highIndex * xStep + 6, width - 60)}
                y={Math.max(yPrice(max) - 4, 12)}
                className="chart-marker__text chart-marker__text--high"
              >
                H {formatPrice(max)}
              </text>
            </g>
          )}

          {/* Low Price Marker */}
          {lowIndex >= 0 && (
            <g className="chart-marker chart-marker--low">
              <circle cx={padX + lowIndex * xStep} cy={yPrice(min)} r={2.5} fill="var(--bad)" />
              <text
                x={Math.min(padX + lowIndex * xStep + 6, width - 60)}
                y={Math.min(yPrice(min) + 12, candleHeight - 4)}
                className="chart-marker__text chart-marker__text--low"
              >
                L {formatPrice(min)}
              </text>
            </g>
          )}

          {/* Current Close Price Guideline */}
          {latestCandle && (
            <g className="chart-live-line">
              <line
                x1={padX}
                x2={width - padX}
                y1={yPrice(latestCandle.close)}
                y2={yPrice(latestCandle.close)}
                className="chart-live-line__stroke"
              />
            </g>
          )}

          {/* Interactive Hover Crosshair */}
          {hoverIndex !== null && (
            <g className="chart-crosshair">
              <line
                x1={padX + hoverIndex * xStep}
                x2={padX + hoverIndex * xStep}
                y1={padTop}
                y2={totalHeight - 8}
                className="chart-crosshair__line"
              />
              {activeCandle && (
                <>
                  <line
                    x1={padX}
                    x2={width - padX}
                    y1={yPrice(activeCandle.close)}
                    y2={yPrice(activeCandle.close)}
                    className="chart-crosshair__line"
                  />
                  <circle
                    cx={padX + hoverIndex * xStep}
                    cy={yPrice(activeCandle.close)}
                    r={3.5}
                    className="chart-crosshair__dot"
                  />
                </>
              )}
            </g>
          )}
        </svg>

        <div className="chart-preview__axis">
          <span>{formatPrice(min)}</span>
          <span className="text-muted">{formatPrice((max + min) / 2)}</span>
          <span>{formatPrice(max)}</span>
        </div>
      </div>
    </div>
  );
}

