import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { TerminalWorkbench } from '../features/terminal/terminal-workbench';
import { DICTIONARY } from '../lib/i18n/dictionary';

const populatedRollingBacktest = {
  ok: true as const,
  data: {
    source: 'eastmoney',
    symbol: '000001',
    timeframe: '1h',
    window: 100,
    bar_count: 80,
    evaluated_windows: 78,
    trade_signals: 5,
    completed_trades: 3,
    wins: 2,
    losses: 1,
    open_trades: 0,
    not_triggered: 0,
    invalid: 0,
    win_rate_pct: 40,
    expectancy_r: 0.5,
    average_r: 1.2,
    total_r: 1.0,
    profit_factor: 1.5,
    max_drawdown_r: 0.3,
    skipped_no_setup: 2,
    skipped_no_followthrough: 1,
    risk_profile: 'aggressive',
    trades: [],
  },
};

// Inject loaded rolling backtest state because SSR renderToStaticMarkup
// does not run useEffect, so async data load never fires.
vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react');
  return {
    ...actual,
    useState: <T>(initial: T | (() => T)): [T, (value: T | ((prev: T) => T)) => void] => {
      if (
        typeof initial === 'object' &&
        initial !== null &&
        'rollingBacktest' in initial &&
        (initial as any).rollingBacktest === null
      ) {
        return [{ ...initial, rollingBacktest: populatedRollingBacktest } as T, vi.fn()];
      }
      return actual.useState(initial);
    },
  };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/terminal',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('next/link', () => ({
  default: ({ children, ...props }: any) => createElement('a', props, children),
}));

vi.mock('../lib/i18n/context', () => ({
  useI18n: () => ({
    locale: 'zh' as const,
    t: DICTIONARY.zh,
    translateLabel: (val: string) => val,
    translateValue: (val: string) => val,
    explainProbability: () => '',
  }),
}));

vi.mock('../../lib/api', () => ({
  api: {
    rollingBacktestSummary: () => populatedRollingBacktest,
    settings: () => ({ ok: true, data: {} }),
    dataSources: () => ({ ok: true, data: {} }),
    klineCache: () => ({ ok: true, data: {} }),
    snapshot: () => ({ ok: true, data: {} }),
  },
  analysisEventsUrl: () => '',
}));

describe('TerminalWorkbench', () => {
  it('renders the rolling backtest dashboard with risk profile in subtitle', () => {
    const html = renderToStaticMarkup(createElement(TerminalWorkbench));

    expect(html).toContain('aggressive');
  });

  it('renders simple-mode risk profile controls', () => {
    const html = renderToStaticMarkup(createElement(TerminalWorkbench));

    expect(html).toContain('风险档位');
    expect(html).toContain('稳健');
    expect(html).toContain('均衡');
    expect(html).toContain('进取');
    expect(html).toContain('强进取');
  });
});
