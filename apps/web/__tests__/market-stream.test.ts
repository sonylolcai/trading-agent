import { describe, expect, it } from 'vitest';
import { MarketStreamEngine } from '../lib/market-stream/stream-engine';
import { DICTIONARY } from '../lib/i18n/dictionary';

describe('MarketStreamEngine & Live Stream', () => {
  it('initializes tickers with reasonable prices and sparklines', () => {
    const engine = new MarketStreamEngine();
    const tickers = engine.getTickers();

    expect(tickers.length).toBeGreaterThanOrEqual(10);
    const btc = tickers.find((t) => t.symbol === 'BTCUSDT');
    expect(btc).toBeDefined();
    expect(btc?.price).toBeGreaterThan(10000);
    expect(btc?.sparkline.length).toBeGreaterThanOrEqual(10);

    engine.destroy();
  });

  it('runs high-frequency simulator and triggers updates', async () => {
    const engine = new MarketStreamEngine();
    engine.setSource('simulator');
    engine.setWhaleThreshold(1000);

    let receivedTrade = false;
    let receivedBook = false;

    engine.onTradeUpdate = (trade) => {
      receivedTrade = true;
      expect(trade.symbol).toBe('BTCUSDT');
      expect(trade.price).toBeGreaterThan(0);
    };

    engine.onOrderBookUpdate = (book) => {
      receivedBook = true;
      expect(book.bids.length).toBeGreaterThan(0);
      expect(book.asks.length).toBeGreaterThan(0);
      expect(book.spread).toBeGreaterThanOrEqual(0);
    };

    engine.start();

    // Wait for a few simulator ticks (runs at ~45ms)
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(receivedTrade).toBe(true);
    expect(receivedBook).toBe(true);

    engine.destroy();
  });

  it('contains proper i18n entries for live stream features', () => {
    expect(DICTIONARY.zh.liveStream).toBe('实时盘口');
    expect(DICTIONARY.en.liveStream).toBe('Live Stream');
    expect(DICTIONARY.zh.orderBook).toBe('L2 深度订单簿');
    expect(DICTIONARY.en.orderBook).toBe('L2 Order Book');
    expect(DICTIONARY.zh.tradeTape).toBe('逐笔成交流水');
  });
});
