import { describe, expect, it } from 'vitest';
import {
  buildCryptoAllocation,
  type CryptoAssetInput,
} from '../lib/crypto-strategy';

const ASSETS: CryptoAssetInput[] = [
  { symbol: 'BTC', name: 'Bitcoin', role: 'Core', momentum: 0.72, volatility: 0.48, fundingPercentile: 58, aboveEma100: true },
  { symbol: 'ETH', name: 'Ethereum', role: 'Core', momentum: 0.41, volatility: 0.66, fundingPercentile: 64, aboveEma100: true },
  { symbol: 'BNB', name: 'BNB', role: 'Satellite', momentum: 0.27, volatility: 0.58, fundingPercentile: 78, aboveEma100: true },
  { symbol: 'XRP', name: 'XRP', role: 'Satellite', momentum: -0.08, volatility: 0.79, fundingPercentile: 45, aboveEma100: false },
  { symbol: 'SOL', name: 'Solana', role: 'Satellite', momentum: 0.55, volatility: 0.91, fundingPercentile: 92, aboveEma100: true },
];

describe('buildCryptoAllocation', () => {
  it('selects at most three eligible assets and respects per-asset caps', () => {
    const result = buildCryptoAllocation(ASSETS, 'risk_on', 0.5);

    expect(result.selectedCount).toBeLessThanOrEqual(3);
    expect(result.grossExposure).toBeLessThanOrEqual(1);
    expect(result.assets.find((asset) => asset.symbol === 'BTC')?.weight).toBeLessThanOrEqual(0.5);
    for (const asset of result.assets.filter((item) => item.symbol !== 'BTC')) {
      expect(asset.weight).toBeLessThanOrEqual(0.25);
    }
  });

  it('excludes negative momentum and below-EMA assets', () => {
    const result = buildCryptoAllocation(ASSETS, 'risk_on', 0.5);
    const xrp = result.assets.find((asset) => asset.symbol === 'XRP');

    expect(xrp?.eligible).toBe(false);
    expect(xrp?.weight).toBe(0);
    expect(xrp?.exclusionReason).toBe('below_ema100');
  });

  it('caps neutral exposure and moves fully to cash in crisis', () => {
    const neutral = buildCryptoAllocation(ASSETS, 'neutral', 0.5);
    const crisis = buildCryptoAllocation(ASSETS, 'crisis', 0.5);

    expect(neutral.grossExposure).toBeLessThanOrEqual(0.5);
    expect(crisis.grossExposure).toBe(0);
    expect(crisis.cashWeight).toBe(1);
    expect(crisis.selectedCount).toBe(0);
  });

  it('reduces exposure when the target volatility is lower', () => {
    const lowRisk = buildCryptoAllocation(ASSETS, 'risk_on', 0.08);
    const highRisk = buildCryptoAllocation(ASSETS, 'risk_on', 0.2);

    expect(lowRisk.grossExposure).toBeLessThan(highRisk.grossExposure);
    expect(lowRisk.estimatedVolatility).toBeLessThanOrEqual(0.080001);
  });
});

