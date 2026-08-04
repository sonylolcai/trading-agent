export type CryptoRegime = 'risk_on' | 'neutral' | 'range' | 'risk_off' | 'crisis';

export type CryptoAssetInput = {
  symbol: string;
  name: string;
  role: string;
  momentum: number;
  volatility: number;
  fundingPercentile: number;
  aboveEma100: boolean;
};

export type CryptoAssetAllocation = CryptoAssetInput & {
  adjustedScore: number;
  eligible: boolean;
  exclusionReason: string | null;
  weight: number;
};

export type CryptoAllocation = {
  regime: CryptoRegime;
  grossCap: number;
  grossExposure: number;
  cashWeight: number;
  estimatedVolatility: number;
  selectedCount: number;
  assets: CryptoAssetAllocation[];
};

const REGIME_GROSS_CAP: Record<CryptoRegime, number> = {
  risk_on: 1,
  neutral: 0.5,
  range: 0.25,
  risk_off: 0.2,
  crisis: 0,
};

const MAX_SELECTED_ASSETS = 3;
const ASSUMED_CORRELATION = 0.65;
const EPSILON = 1e-9;

function assetCap(symbol: string): number {
  return symbol.toUpperCase() === 'BTC' ? 0.5 : 0.25;
}

function fundingPenalty(percentile: number): number {
  if (percentile >= 90) {
    return 0.5;
  }
  if (percentile >= 75) {
    return 0.8;
  }
  return 1;
}

function exclusionReason(asset: CryptoAssetInput): string | null {
  if (!Number.isFinite(asset.volatility) || asset.volatility <= 0) {
    return 'invalid_volatility';
  }
  if (!asset.aboveEma100) {
    return 'below_ema100';
  }
  if (!Number.isFinite(asset.momentum) || asset.momentum <= 0) {
    return 'momentum_not_positive';
  }
  return null;
}

function allocateWithCaps(
  candidates: Array<{ symbol: string; score: number }>,
  targetGross: number,
): Map<string, number> {
  const weights = new Map<string, number>();
  let remaining = targetGross;
  let active = [...candidates];

  while (active.length > 0 && remaining > EPSILON) {
    const scoreTotal = active.reduce((total, item) => total + item.score, 0);
    if (scoreTotal <= EPSILON) {
      break;
    }

    const capped = active.filter((item) => {
      const proposed = remaining * item.score / scoreTotal;
      const room = assetCap(item.symbol) - (weights.get(item.symbol) ?? 0);
      return proposed >= room - EPSILON;
    });

    if (capped.length === 0) {
      for (const item of active) {
        weights.set(
          item.symbol,
          (weights.get(item.symbol) ?? 0) + remaining * item.score / scoreTotal,
        );
      }
      remaining = 0;
      break;
    }

    const cappedSymbols = new Set(capped.map((item) => item.symbol));
    for (const item of capped) {
      const current = weights.get(item.symbol) ?? 0;
      const room = Math.max(0, assetCap(item.symbol) - current);
      weights.set(item.symbol, current + room);
      remaining -= room;
    }
    active = active.filter((item) => !cappedSymbols.has(item.symbol));
  }

  return weights;
}

function estimatePortfolioVolatility(
  assets: CryptoAssetInput[],
  weights: Map<string, number>,
): number {
  let variance = 0;

  for (let i = 0; i < assets.length; i += 1) {
    const left = assets[i];
    const leftWeight = weights.get(left.symbol) ?? 0;
    variance += leftWeight ** 2 * left.volatility ** 2;

    for (let j = i + 1; j < assets.length; j += 1) {
      const right = assets[j];
      const rightWeight = weights.get(right.symbol) ?? 0;
      variance += (
        2
        * ASSUMED_CORRELATION
        * leftWeight
        * rightWeight
        * left.volatility
        * right.volatility
      );
    }
  }

  return Math.sqrt(Math.max(0, variance));
}

export function buildCryptoAllocation(
  assets: CryptoAssetInput[],
  regime: CryptoRegime,
  targetVolatility: number,
): CryptoAllocation {
  const grossCap = REGIME_GROSS_CAP[regime];
  const evaluated = assets.map((asset) => {
    const reason = exclusionReason(asset);
    const adjustedScore = reason
      ? 0
      : asset.momentum * fundingPenalty(asset.fundingPercentile) / asset.volatility;
    return {
      ...asset,
      adjustedScore,
      eligible: reason === null,
      exclusionReason: reason,
    };
  });

  const selected = [...evaluated]
    .filter((asset) => asset.eligible)
    .sort((left, right) => right.adjustedScore - left.adjustedScore)
    .slice(0, MAX_SELECTED_ASSETS);

  const maxWeights = allocateWithCaps(
    selected.map((asset) => ({ symbol: asset.symbol, score: asset.adjustedScore })),
    grossCap,
  );
  const maxVolatility = estimatePortfolioVolatility(assets, maxWeights);
  const volatilityScale = maxVolatility > 0
    ? Math.min(1, Math.max(0, targetVolatility) / maxVolatility)
    : 0;
  const finalWeights = new Map(
    [...maxWeights].map(([symbol, weight]) => [symbol, weight * volatilityScale]),
  );
  const grossExposure = [...finalWeights.values()].reduce((total, weight) => total + weight, 0);
  const estimatedVolatility = estimatePortfolioVolatility(assets, finalWeights);

  return {
    regime,
    grossCap,
    grossExposure,
    cashWeight: Math.max(0, 1 - grossExposure),
    estimatedVolatility,
    selectedCount: [...finalWeights.values()].filter((weight) => weight > EPSILON).length,
    assets: evaluated.map((asset) => ({
      ...asset,
      weight: finalWeights.get(asset.symbol) ?? 0,
    })),
  };
}
