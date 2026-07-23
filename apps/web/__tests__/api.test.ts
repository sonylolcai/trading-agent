import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../lib/api';

describe('api', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('patches the simple risk profile setting', async () => {
    const fetchMock = vi.fn(async () => (
      new Response(JSON.stringify({ general: { decision_stance: 'aggressive' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    ));
    vi.stubGlobal('fetch', fetchMock);

    const result = await api.updateRiskProfile({ risk_profile: 'aggressive' });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/api/settings/risk-profile',
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ risk_profile: 'aggressive' }),
      }),
    );
  });

  it('requests a rolling price-versus-volume comparison', async () => {
    const fetchMock = vi.fn(async () => (
      new Response(JSON.stringify({ price_only: {}, volume_assisted: {}, delta: {} }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    ));
    vi.stubGlobal('fetch', fetchMock);

    const result = await api.rollingBacktestComparison({ window: 30 });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/api/backtest/rolling-comparison?window=30',
      expect.objectContaining({ cache: 'no-store' }),
    );
  });
});
