import type {
  CandleDataPoint,
  OrderBookData,
  OrderBookLevel,
  StreamDataSource,
  StreamMetrics,
  TickerItem,
  TradeItem,
} from './types';

export const INITIAL_SYMBOLS = [
  { symbol: 'BTCUSDT', name: 'Bitcoin', basePrice: 78040.0, okxId: 'BTC-USDT' },
  { symbol: 'ETHUSDT', name: 'Ethereum', basePrice: 3150.0, okxId: 'ETH-USDT' },
  { symbol: 'SOLUSDT', name: 'Solana', basePrice: 185.0, okxId: 'SOL-USDT' },
  { symbol: 'BNBUSDT', name: 'BNB', basePrice: 615.0, okxId: 'BNB-USDT' },
  { symbol: 'XRPUSDT', name: 'Ripple', basePrice: 0.584, okxId: 'XRP-USDT' },
  { symbol: 'DOGEUSDT', name: 'Dogecoin', basePrice: 0.165, okxId: 'DOGE-USDT' },
  { symbol: 'ADAUSDT', name: 'Cardano', basePrice: 0.385, okxId: 'ADA-USDT' },
  { symbol: 'AVAXUSDT', name: 'Avalanche', basePrice: 28.4, okxId: 'AVAX-USDT' },
  { symbol: 'SUIUSDT', name: 'Sui', basePrice: 2.10, okxId: 'SUI-USDT' },
  { symbol: 'LINKUSDT', name: 'Chainlink', basePrice: 13.5, okxId: 'LINK-USDT' },
  { symbol: 'NEARUSDT', name: 'NEAR Protocol', basePrice: 5.40, okxId: 'NEAR-USDT' },
  { symbol: 'APTUSDT', name: 'Aptos', basePrice: 8.85, okxId: 'APT-USDT' },
];


export class MarketStreamEngine {
  private currentSource: StreamDataSource = 'binance';
  private currentSymbol: string = 'BTCUSDT';
  private whaleThresholdUsdt: number = 5000;
  private ws: WebSocket | null = null;
  private simTimer: any = null;
  private tpsTimer: any = null;
  private messageCounter = 0;
  private lastTpsCount = 0;
  private currentTps = 0;
  private currentLatency = 16;
  private isDestroyed = false;

  private tickersMap: Map<string, TickerItem> = new Map();
  private recentCandles: CandleDataPoint[] = [];

  // Callbacks
  public onTickersUpdate?: (tickers: TickerItem[]) => void;
  public onOrderBookUpdate?: (book: OrderBookData) => void;
  public onTradeUpdate?: (trade: TradeItem) => void;
  public onMetricsUpdate?: (metrics: StreamMetrics) => void;

  constructor() {
    this.initDefaultTickers();
    this.startTpsSampler();
  }

  private initDefaultTickers() {
    for (const item of INITIAL_SYMBOLS) {
      const sparkline: number[] = [];
      let p = item.basePrice;
      for (let i = 0; i < 20; i++) {
        p += (Math.random() - 0.49) * (item.basePrice * 0.005);
        sparkline.push(p);
      }
      const change24hPct = (Math.random() * 8 - 3.5);
      const change24h = (item.basePrice * change24hPct) / 100;
      this.tickersMap.set(item.symbol, {
        symbol: item.symbol,
        name: item.name,
        price: item.basePrice,
        prevPrice: item.basePrice,
        change24h,
        change24hPct,
        high24h: item.basePrice * 1.04,
        low24h: item.basePrice * 0.96,
        volume24h: Math.floor(Math.random() * 50000 + 10000),
        quoteVolume24h: Math.floor(item.basePrice * (Math.random() * 50000 + 10000)),
        sparkline,
        direction: 'none',
        lastUpdated: Date.now(),
      });
    }
  }

  public getTickers(): TickerItem[] {
    return Array.from(this.tickersMap.values());
  }

  public setWhaleThreshold(threshold: number) {
    this.whaleThresholdUsdt = threshold;
  }

  public setSymbol(symbol: string) {
    if (this.currentSymbol === symbol) return;
    this.currentSymbol = symbol;
    if (this.currentSource !== 'simulator') {
      this.reconnect();
    }
  }

  public setSource(source: StreamDataSource) {
    if (this.currentSource === source && this.ws?.readyState === WebSocket.OPEN) return;
    this.currentSource = source;
    this.reconnect();
  }

  public start() {
    this.reconnect();
  }

  public stop() {
    this.cleanupCurrentSource();
  }

  public destroy() {
    this.isDestroyed = true;
    this.stop();
    if (this.tpsTimer) clearInterval(this.tpsTimer);
  }

  private startTpsSampler() {
    this.tpsTimer = setInterval(() => {
      if (this.isDestroyed) return;
      this.currentTps = this.messageCounter - this.lastTpsCount;
      this.lastTpsCount = this.messageCounter;

      this.onMetricsUpdate?.({
        tps: this.currentTps,
        latencyMs: this.currentLatency,
        totalMessages: this.messageCounter,
        bufferKb: Math.round((this.messageCounter * 0.08) % 4096),
        status: this.currentSource === 'simulator' ? 'connected' : (this.ws && this.ws.readyState === WebSocket.OPEN ? 'connected' : 'connecting'),
        source: this.currentSource,
      });
    }, 1000);
  }

  private cleanupCurrentSource() {
    if (this.ws) {
      try {
        this.ws.onopen = null;
        this.ws.onmessage = null;
        this.ws.onerror = null;
        this.ws.onclose = null;
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
    if (this.simTimer) {
      clearInterval(this.simTimer);
      this.simTimer = null;
    }
  }

  private reconnect() {
    this.cleanupCurrentSource();
    if (this.isDestroyed) return;

    if (this.currentSource === 'simulator') {
      this.startSimulator();
    } else if (this.currentSource === 'binance') {
      this.startBinance();
    } else if (this.currentSource === 'okx') {
      this.startOkx();
    }
  }

  // ==================== BINANCE WEBSOCKET ====================
  private startBinance() {
    const symLower = this.currentSymbol.toLowerCase();
    // Subscribe to multi-stream: all miniTickers + target symbol trade + depth20
    const streams = `!miniTicker@arr/${symLower}@trade/${symLower}@depth20@100ms`;
    const url = `wss://stream.binance.com:9443/stream?streams=${streams}`;

    try {
      this.ws = new WebSocket(url);
    } catch {
      this.fallbackToSimulator();
      return;
    }

    const connectTimeout = setTimeout(() => {
      if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
        this.fallbackToSimulator();
      }
    }, 4000);

    this.ws.onopen = () => {
      clearTimeout(connectTimeout);
      this.currentLatency = Math.floor(Math.random() * 20 + 20);
    };

    this.ws.onmessage = (event) => {
      this.messageCounter++;
      try {
        const payload = JSON.parse(event.data);
        const stream: string = payload.stream ?? '';
        const data = payload.data;

        if (stream === '!miniTicker@arr' && Array.isArray(data)) {
          this.handleBinanceMiniTickers(data);
        } else if (stream.endsWith('@trade')) {
          this.handleBinanceTrade(data);
        } else if (stream.includes('@depth')) {
          this.handleBinanceDepth(data);
        }
      } catch {
        // ignore malformed frame
      }
    };

    this.ws.onerror = () => {
      clearTimeout(connectTimeout);
      this.fallbackToSimulator();
    };

    this.ws.onclose = () => {
      clearTimeout(connectTimeout);
    };
  }

  private handleBinanceMiniTickers(items: any[]) {
    let hasChanges = false;
    const now = Date.now();

    for (const raw of items) {
      const symbol = raw.s;
      const current = this.tickersMap.get(symbol);
      if (!current) continue;

      const price = parseFloat(raw.c);
      const high = parseFloat(raw.h);
      const low = parseFloat(raw.l);
      const volume = parseFloat(raw.v);
      const quoteVol = parseFloat(raw.q);
      const open = parseFloat(raw.o);
      const change24h = price - open;
      const change24hPct = open > 0 ? (change24h / open) * 100 : 0;

      const prev = current.price;
      const dir = price > prev ? 'up' : price < prev ? 'down' : 'none';

      const sparkline = [...current.sparkline.slice(-24), price];

      this.tickersMap.set(symbol, {
        ...current,
        price,
        prevPrice: prev,
        change24h,
        change24hPct,
        high24h: high,
        low24h: low,
        volume24h: volume,
        quoteVolume24h: quoteVol,
        sparkline,
        direction: dir,
        lastUpdated: now,
      });
      hasChanges = true;
    }

    if (hasChanges && this.onTickersUpdate) {
      this.onTickersUpdate(Array.from(this.tickersMap.values()));
    }
  }

  private handleBinanceTrade(raw: any) {
    const price = parseFloat(raw.p);
    const amount = parseFloat(raw.q);
    const total = price * amount;
    const side: 'buy' | 'sell' = raw.m ? 'sell' : 'buy'; // in Binance: m is buyer is market maker -> sell order
    const isWhale = total >= this.whaleThresholdUsdt;

    const trade: TradeItem = {
      id: String(raw.t ?? raw.E),
      symbol: this.currentSymbol,
      price,
      amount,
      total,
      side,
      time: raw.T ?? Date.now(),
      isWhale,
    };

    this.onTradeUpdate?.(trade);
  }

  private handleBinanceDepth(raw: any) {
    const rawBids: [string, string][] = raw.bids || [];
    const rawAsks: [string, string][] = raw.asks || [];

    let bidCum = 0;
    const bids: OrderBookLevel[] = rawBids.slice(0, 12).map(([p, a]) => {
      const price = parseFloat(p);
      const amount = parseFloat(a);
      bidCum += amount;
      return { price, amount, total: bidCum, percent: 0 };
    });

    let askCum = 0;
    const asks: OrderBookLevel[] = rawAsks.slice(0, 12).map(([p, a]) => {
      const price = parseFloat(p);
      const amount = parseFloat(a);
      askCum += amount;
      return { price, amount, total: askCum, percent: 0 };
    });

    const maxCum = Math.max(bidCum, askCum, 1);
    bids.forEach((b) => (b.percent = Math.min(100, Math.round((b.total / maxCum) * 100))));
    asks.forEach((a) => (a.percent = Math.min(100, Math.round((a.total / maxCum) * 100))));

    const topBid = bids[0]?.price ?? 0;
    const topAsk = asks[0]?.price ?? 0;
    const spread = Math.max(0, topAsk - topBid);
    const spreadPct = topBid > 0 ? (spread / topBid) * 100 : 0;

    this.onOrderBookUpdate?.({
      symbol: this.currentSymbol,
      bids,
      asks,
      spread,
      spreadPct,
      lastUpdated: Date.now(),
    });
  }

  // ==================== OKX WEBSOCKET ====================
  private startOkx() {
    const okxSymbol = INITIAL_SYMBOLS.find((s) => s.symbol === this.currentSymbol)?.okxId ?? 'BTC-USDT';
    const url = 'wss://ws.okx.com:8443/ws/v5/public';

    try {
      this.ws = new WebSocket(url);
    } catch {
      this.fallbackToSimulator();
      return;
    }

    const connectTimeout = setTimeout(() => {
      if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
        this.fallbackToSimulator();
      }
    }, 4000);

    this.ws.onopen = () => {
      clearTimeout(connectTimeout);
      this.currentLatency = Math.floor(Math.random() * 25 + 30);
      const subMsg = {
        op: 'subscribe',
        args: [
          { channel: 'tickers', instId: okxSymbol },
          { channel: 'books5', instId: okxSymbol },
          { channel: 'trades', instId: okxSymbol },
        ],
      };
      this.ws?.send(JSON.stringify(subMsg));
    };

    this.ws.onmessage = (event) => {
      this.messageCounter++;
      try {
        const payload = JSON.parse(event.data);
        const channel = payload.arg?.channel;
        const data = payload.data;
        if (!data || !Array.isArray(data) || data.length === 0) return;

        if (channel === 'trades') {
          const raw = data[0];
          const price = parseFloat(raw.px);
          const amount = parseFloat(raw.sz);
          const total = price * amount;
          this.onTradeUpdate?.({
            id: raw.tradeId,
            symbol: this.currentSymbol,
            price,
            amount,
            total,
            side: raw.side === 'buy' ? 'buy' : 'sell',
            time: parseInt(raw.ts, 10),
            isWhale: total >= this.whaleThresholdUsdt,
          });
        } else if (channel === 'books5') {
          const raw = data[0];
          this.handleOkxDepth(raw);
        }
      } catch {
        // ignore
      }
    };

    this.ws.onerror = () => {
      clearTimeout(connectTimeout);
      this.fallbackToSimulator();
    };
  }

  private handleOkxDepth(raw: any) {
    const rawBids: [string, string, string, string][] = raw.bids || [];
    const rawAsks: [string, string, string, string][] = raw.asks || [];

    let bidCum = 0;
    const bids: OrderBookLevel[] = rawBids.slice(0, 10).map((b) => {
      const price = parseFloat(b[0]);
      const amount = parseFloat(b[1]);
      bidCum += amount;
      return { price, amount, total: bidCum, percent: 0 };
    });

    let askCum = 0;
    const asks: OrderBookLevel[] = rawAsks.slice(0, 10).map((a) => {
      const price = parseFloat(a[0]);
      const amount = parseFloat(a[1]);
      askCum += amount;
      return { price, amount, total: askCum, percent: 0 };
    });

    const maxCum = Math.max(bidCum, askCum, 1);
    bids.forEach((b) => (b.percent = Math.min(100, Math.round((b.total / maxCum) * 100))));
    asks.forEach((a) => (a.percent = Math.min(100, Math.round((a.total / maxCum) * 100))));

    const topBid = bids[0]?.price ?? 0;
    const topAsk = asks[0]?.price ?? 0;
    const spread = Math.max(0, topAsk - topBid);
    const spreadPct = topBid > 0 ? (spread / topBid) * 100 : 0;

    this.onOrderBookUpdate?.({
      symbol: this.currentSymbol,
      bids,
      asks,
      spread,
      spreadPct,
      lastUpdated: Date.now(),
    });
  }

  // ==================== SIMULATOR (HIGH-SPEED STRESS TEST) ====================
  private fallbackToSimulator() {
    this.currentSource = 'simulator';
    this.startSimulator();
  }

  private startSimulator() {
    this.cleanupCurrentSource();
    this.currentLatency = Math.floor(Math.random() * 8 + 6);

    let activePrice = this.tickersMap.get(this.currentSymbol)?.price ?? 68000;

    // High frequency interval: 30ms -> produces ~33 ticks/sec from trades + tickers = 100+ events/sec
    this.simTimer = setInterval(() => {
      if (this.isDestroyed) return;
      this.messageCounter += 2;

      // 1. Tick updates for random symbol
      const randomItem = INITIAL_SYMBOLS[Math.floor(Math.random() * INITIAL_SYMBOLS.length)];
      const current = this.tickersMap.get(randomItem.symbol);
      if (current) {
        const delta = (Math.random() - 0.495) * (current.price * 0.001);
        const nextPrice = Math.max(0.0001, current.price + delta);
        const dir = nextPrice > current.price ? 'up' : 'down';
        const sparkline = [...current.sparkline.slice(-24), nextPrice];
        const change24hPct = current.change24hPct + (delta / current.price) * 10;

        this.tickersMap.set(randomItem.symbol, {
          ...current,
          price: nextPrice,
          prevPrice: current.price,
          direction: dir,
          sparkline,
          change24hPct,
          lastUpdated: Date.now(),
        });

        if (randomItem.symbol === this.currentSymbol) {
          activePrice = nextPrice;
        }
      }

      this.onTickersUpdate?.(Array.from(this.tickersMap.values()));

      // 2. High-frequency trade on current symbol
      const side: 'buy' | 'sell' = Math.random() > 0.48 ? 'buy' : 'sell';
      const isBigWhale = Math.random() < 0.08;
      const amount = isBigWhale
        ? Math.random() * 4 + 1.2
        : Math.random() * 0.35 + 0.01;
      const tradePrice = activePrice + (Math.random() - 0.5) * (activePrice * 0.0004);
      const total = tradePrice * amount;

      this.onTradeUpdate?.({
        id: `sim-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        symbol: this.currentSymbol,
        price: tradePrice,
        amount,
        total,
        side,
        time: Date.now(),
        isWhale: total >= this.whaleThresholdUsdt,
      });

      // 3. Generate Order Book Depth
      const bids: OrderBookLevel[] = [];
      const asks: OrderBookLevel[] = [];
      let bidCum = 0;
      let askCum = 0;
      const tickSpread = activePrice * 0.0001;

      for (let i = 1; i <= 12; i++) {
        const bPrice = activePrice - i * tickSpread * (0.8 + Math.random() * 0.4);
        const bAmt = Math.random() * 1.5 + 0.1;
        bidCum += bAmt;
        bids.push({ price: bPrice, amount: bAmt, total: bidCum, percent: 0 });

        const aPrice = activePrice + i * tickSpread * (0.8 + Math.random() * 0.4);
        const aAmt = Math.random() * 1.5 + 0.1;
        askCum += aAmt;
        asks.push({ price: aPrice, amount: aAmt, total: askCum, percent: 0 });
      }

      const maxCum = Math.max(bidCum, askCum, 1);
      bids.forEach((b) => (b.percent = Math.round((b.total / maxCum) * 100)));
      asks.forEach((a) => (a.percent = Math.round((a.total / maxCum) * 100)));

      this.onOrderBookUpdate?.({
        symbol: this.currentSymbol,
        bids,
        asks,
        spread: asks[0].price - bids[0].price,
        spreadPct: ((asks[0].price - bids[0].price) / bids[0].price) * 100,
        lastUpdated: Date.now(),
      });
    }, 45);
  }
}
