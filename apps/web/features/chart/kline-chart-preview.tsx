import { toChartCandles } from '../../lib/chart';
import type { KlineFramePayload } from '../../types/api';

type KlineChartPreviewProps = {
  frame?: KlineFramePayload;
};

export function KlineChartPreview({ frame }: KlineChartPreviewProps) {
  if (!frame || frame.bars.length === 0) {
    return <div className="empty-state">No cached K-line frame available.</div>;
  }

  const candles = toChartCandles(frame).slice(-64);
  const highs = candles.map((bar) => bar.high);
  const lows = candles.map((bar) => bar.low);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const spread = Math.max(max - min, 0.0001);
  const width = Math.max(candles.length * 9, 320);
  const height = 220;
  const pad = 14;
  const xStep = (width - pad * 2) / Math.max(candles.length - 1, 1);
  const y = (price: number) => pad + ((max - price) / spread) * (height - pad * 2);

  return (
    <div className="chart-preview" aria-label={`${frame.symbol} ${frame.timeframe} candle preview`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" preserveAspectRatio="none">
        <line className="chart-preview__grid" x1={pad} x2={width - pad} y1={y(max)} y2={y(max)} />
        <line className="chart-preview__grid" x1={pad} x2={width - pad} y1={y(min)} y2={y(min)} />
        {candles.map((bar, index) => {
          const x = pad + index * xStep;
          const up = bar.close >= bar.open;
          const bodyTop = y(Math.max(bar.open, bar.close));
          const bodyBottom = y(Math.min(bar.open, bar.close));
          const bodyHeight = Math.max(bodyBottom - bodyTop, 2);
          return (
            <g key={`${bar.seq}-${bar.time}`} className={up ? 'candle candle--up' : 'candle candle--down'}>
              <line x1={x} x2={x} y1={y(bar.high)} y2={y(bar.low)} />
              <rect x={x - 3} y={bodyTop} width={6} height={bodyHeight} rx={1} />
            </g>
          );
        })}
      </svg>
      <div className="chart-preview__axis">
        <span>{min.toFixed(2)}</span>
        <span>{max.toFixed(2)}</span>
      </div>
    </div>
  );
}
