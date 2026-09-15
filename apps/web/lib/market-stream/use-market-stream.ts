'use client';

import { useEffect, useRef, useState } from 'react';
import { MarketStreamEngine } from './stream-engine';
import type {
  OrderBookData,
  StreamDataSource,
  StreamMetrics,
  ThrottleRate,
  TickerItem,
  TradeItem,
} from './types';

const defaultMetrics: StreamMetrics = {
  tps: 0,
  latencyMs: 16,
  totalMessages: 0,
  bufferKb: 0,
  status: 'connecting',
  source: 'binance',
};

const defaultOrderBook: OrderBookData = {
  symbol: 'BTCUSDT',
  bids: [],
  asks: [],
  spread: 0,
  spreadPct: 0,
  lastUpdated: 0,
};

export function useMarketStream(initialSymbol = 'BTCUSDT') {
  const engineRef = useRef<MarketStreamEngine | null>(null);

  const [symbol, setSymbolState] = useState(initialSymbol);
  const [source, setSourceState] = useState<StreamDataSource>('binance');
  const [throttle, setThrottleState] = useState<ThrottleRate>('realtime');
  const [whaleThreshold, setWhaleThresholdState] = useState(5000);

  const [tickers, setTickers] = useState<TickerItem[]>([]);
  const [orderBook, setOrderBook] = useState<OrderBookData>(defaultOrderBook);
  const [trades, setTrades] = useState<TradeItem[]>([]);
  const [metrics, setMetrics] = useState<StreamMetrics>(defaultMetrics);

  // Buffer refs for throttling
  const bufferTickersRef = useRef<TickerItem[] | null>(null);
  const bufferBookRef = useRef<OrderBookData | null>(null);
  const bufferTradesRef = useRef<TradeItem[]>([]);
  const throttleRef = useRef<ThrottleRate>(throttle);

  useEffect(() => {
    throttleRef.current = throttle;
    if (throttle === 'realtime') {
      if (bufferTickersRef.current) {
        setTickers(bufferTickersRef.current);
        bufferTickersRef.current = null;
      }
      if (bufferBookRef.current) {
        setOrderBook(bufferBookRef.current);
        bufferBookRef.current = null;
      }
      if (bufferTradesRef.current.length > 0) {
        setTrades((prev) => [...bufferTradesRef.current, ...prev].slice(0, 60));
        bufferTradesRef.current = [];
      }
    }
  }, [throttle]);

  useEffect(() => {
    const engine = new MarketStreamEngine();
    engineRef.current = engine;
    engine.setSymbol(symbol);
    engine.setSource(source);
    engine.setWhaleThreshold(whaleThreshold);

    // Initial tickers
    setTickers(engine.getTickers());

    engine.onTickersUpdate = (updated) => {
      if (throttleRef.current === 'realtime') {
        setTickers(updated);
      } else {
        bufferTickersRef.current = updated;
      }
    };

    engine.onOrderBookUpdate = (book) => {
      if (throttleRef.current === 'realtime') {
        setOrderBook(book);
      } else {
        bufferBookRef.current = book;
      }
    };

    engine.onTradeUpdate = (trade) => {
      if (throttleRef.current === 'realtime') {
        setTrades((prev) => [trade, ...prev.slice(0, 59)]);
      } else {
        bufferTradesRef.current.unshift(trade);
        if (bufferTradesRef.current.length > 60) {
          bufferTradesRef.current.pop();
        }
      }
    };

    engine.onMetricsUpdate = (m) => {
      setMetrics(m);
    };

    engine.start();

    return () => {
      engine.destroy();
      engineRef.current = null;
    };
  }, []); // Run once on mount

  // Throttle flusher
  useEffect(() => {
    if (throttle === 'realtime') return undefined;

    const ms = throttle === '100ms' ? 100 : throttle === '250ms' ? 250 : 500;
    const interval = setInterval(() => {
      if (bufferTickersRef.current) {
        setTickers(bufferTickersRef.current);
        bufferTickersRef.current = null;
      }
      if (bufferBookRef.current) {
        setOrderBook(bufferBookRef.current);
        bufferBookRef.current = null;
      }
      if (bufferTradesRef.current.length > 0) {
        setTrades((prev) => {
          const merged = [...bufferTradesRef.current, ...prev].slice(0, 60);
          bufferTradesRef.current = [];
          return merged;
        });
      }
    }, ms);

    return () => clearInterval(interval);
  }, [throttle]);

  const selectSymbol = (sym: string) => {
    setSymbolState(sym);
    setTrades([]);
    engineRef.current?.setSymbol(sym);
  };

  const selectSource = (src: StreamDataSource) => {
    setSourceState(src);
    engineRef.current?.setSource(src);
  };

  const selectThrottle = (rate: ThrottleRate) => {
    setThrottleState(rate);
  };

  const updateWhaleThreshold = (val: number) => {
    setWhaleThresholdState(val);
    engineRef.current?.setWhaleThreshold(val);
  };

  return {
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
  };
}
