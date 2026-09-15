export type StreamDataSource = 'binance' | 'okx' | 'simulator';

export type TickerItem = {
  symbol: string;
  name: string;
  price: number;
  prevPrice: number;
  change24h: number;
  change24hPct: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  quoteVolume24h: number;
  sparkline: number[];
  direction: 'up' | 'down' | 'none';
  lastUpdated: number;
};

export type OrderBookLevel = {
  price: number;
  amount: number;
  total: number;
  percent: number;
};

export type OrderBookData = {
  symbol: string;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  spread: number;
  spreadPct: number;
  lastUpdated: number;
};

export type TradeItem = {
  id: string;
  symbol: string;
  price: number;
  amount: number;
  total: number;
  side: 'buy' | 'sell';
  time: number;
  isWhale: boolean;
};

export type StreamMetrics = {
  tps: number;
  latencyMs: number;
  totalMessages: number;
  bufferKb: number;
  status: 'connected' | 'connecting' | 'disconnected' | 'error';
  source: StreamDataSource;
};

export type CandleDataPoint = {
  time: number; // unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type ThrottleRate = 'realtime' | '100ms' | '250ms' | '500ms';
