import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { HistoryPage } from '../features/history/history-page';
import type { RecordSummary } from '../types/api';
import { DICTIONARY, translateKnownLabel, translateKnownValue, probabilityExplanation } from '../lib/i18n/dictionary';

let mockLocale: 'zh' | 'en' = 'zh';

vi.mock('../lib/i18n/context', () => ({
  useI18n: () => ({
    locale: mockLocale,
    t: DICTIONARY[mockLocale],
    translateLabel: (val: string) => translateKnownLabel(val, mockLocale),
    translateValue: (val: string) => translateKnownValue(val, mockLocale),
    explainProbability: (val: string) => probabilityExplanation(val, mockLocale),
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/history',
  useSearchParams: () => new URLSearchParams(),
}));

const records: RecordSummary[] = [
  {
    id: 'record-1',
    timestamp_local_iso: '2026-06-25T10:00:00.000',
    timestamp_local_ms: 1,
    symbol: '000001',
    timeframe: '1h',
    bar_count: 100,
    decision_stance: 'balanced',
    decision_confidence_threshold: 40,
    action: '不下单',
    direction: '',
    has_exception: false,
    analysis_report: {
      headline: { action: '不下单', summary: '等待确认。' },
      metrics: [],
      decision: {
        risk_profile: 'balanced',
        signal_threshold: 40,
        terminal: { outcome: 'wait' },
      },
      evidence_tables: [],
      flows: [],
      probability_blocks: [],
      lists: [],
    },
  },
  {
    id: 'record-2',
    timestamp_local_iso: '2026-06-25T11:00:00.000',
    timestamp_local_ms: 2,
    symbol: '600519',
    timeframe: '1d',
    bar_count: 100,
    decision_stance: 'aggressive',
    decision_confidence_threshold: 30,
    action: '限价单',
    direction: '',
    has_exception: false,
    analysis_report: {
      headline: { action: '限价单', summary: '边界限价。' },
      metrics: [],
      decision: {
        risk_profile: 'aggressive',
        signal_threshold: 30,
        terminal: { outcome: 'trade' },
      },
      evidence_tables: [],
      flows: [],
      probability_blocks: [],
      lists: [],
    },
  },
];

describe('HistoryPage', () => {
  it('renders complete reports in single-open accordion panels', () => {
    const html = renderToStaticMarkup(
      createElement(HistoryPage, { initialRecords: records, initialOpenId: 'record-1' } as any),
    );

    const expandedCount = (html.match(/data-history-expanded="true"/g) ?? []).length;
    expect(expandedCount).toBe(1);
    expect(html).toContain('完整分析报告');
    expect(html).toContain('等待确认。');
    expect(html).toContain('风险档位');
    expect(html).not.toContain('<table');
    expect(html).not.toContain('<th>Direction</th>');
  });
});
