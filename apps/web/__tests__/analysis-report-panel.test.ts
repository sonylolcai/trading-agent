import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { AnalysisReportPanel } from '../features/analysis/analysis-report-panel';
import type { AnalysisRecordPayload } from '../types/api';
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

describe('AnalysisReportPanel', () => {
  it('renders a productized report without raw JSON fragments', () => {
    const record: AnalysisRecordPayload = {
      stage1_diagnosis: {
        direction: 'bullish',
        diagnosis_confidence: 70,
        key_signals: ['EMA support'],
        bar_by_bar_summary: [
          {
            bar: 'K1',
            role: 'signal',
            bar_type: 'trend_bull',
            context_effect: 'strengthens_bull',
            reason: 'Strong close.',
          },
        ],
      },
      stage2_decision: {
        decision: {
          order_type: 'market',
          order_direction: 'long',
          trade_confidence: 62,
          key_factors: ['Fresh signal bar'],
          watch_points: ['K1 follow-through'],
        },
        terminal: { node_id: '10.3', outcome: 'trade', label: 'trigger' },
        decision_trace: [
          {
            node_id: '10.3',
            question: 'Does K1 confirm?',
            answer: 'yes',
            reason: 'K1 closed near high.',
            bar_range: 'K1',
          },
        ],
        next_bar_prediction: {
          direction: 'bullish',
          probabilities: { bullish: 62, bearish: 18, neutral: 20 },
          reasoning: 'Continuation has edge.',
          unpredictable: false,
          features_used: ['stage1_diagnosis'],
        },
        next_cycle_prediction: {
          cycle: 'normal_channel',
          direction: 'bullish',
          probabilities: { normal_channel: 68, trading_range: 32 },
          reasoning: 'Channel structure remains intact.',
        },
      },
    };

    const html = renderToStaticMarkup(createElement(AnalysisReportPanel, { record }));

    expect(html).toContain('交易信心');
    expect(html).toContain('决策树可视化');
    expect(html).toContain('aria-expanded="true"');
    expect(html).not.toContain('<h3>决策路径</h3>');
    expect(html).toContain('Does K1 confirm?');
    expect(html).toContain('逐K线流程');
    expect(html).toContain('Fresh signal bar');
    expect(html).toContain('style="width:62%"');
    expect(html).toContain('下一周期预测');
    expect(html).toContain('正常通道');
    expect(html).toContain('趋势通道');
    expect(html).not.toContain('{"node_id"');
    expect(html).not.toContain('[&quot;EMA support&quot;');
  });

  it('can render the report in English when requested', () => {
    mockLocale = 'en';
    const record: AnalysisRecordPayload = {
      stage1_diagnosis: {
        direction: 'bullish',
        diagnosis_confidence: 70,
        key_signals: ['EMA support'],
        bar_by_bar_summary: [],
      },
      stage2_decision: {
        order_type: 'buy_limit',
        trigger_condition: 'EMA touch',
        estimated_win_rate: 65,
        estimated_rr: 1.5,
        position_size: 1,
        decision_tree_trace: [],
        stop_loss: 0,
        take_profit: 0,
        risk_management: 'trail stop',
        entry_point: 0,
        reasoning: 'Testing english render',
      },
    };
    const html = renderToStaticMarkup(createElement(AnalysisReportPanel, { record }));

    // Reset back for other tests
    mockLocale = 'zh';

    expect(html).toContain('buy_limit');
    expect(html).toContain('buy_limit');
    // Ensure English copy is used for sections
    // Tree is empty, so it won't render Decision Tree section.
    expect(html).toContain(DICTIONARY.en.keyFactors);
  });

  it('renders no-order actions with a cautious status tone', () => {
    const record: AnalysisRecordPayload = {
      analysis_report: {
        headline: {
          action: '不下单',
          direction: null,
          summary: '等待有效信号确认。',
        },
        metrics: [],
        decision: {
          order_type: '不下单',
          terminal: { outcome: 'wait' },
        },
        evidence_tables: [],
        flows: [],
        probability_blocks: [],
        lists: [],
      },
    };

    const html = renderToStaticMarkup(createElement(AnalysisReportPanel, { record }));

    expect(html).toContain('不下单');
    expect(html).toContain('status-chip--warn');
    expect(html).not.toContain('status-chip--good">不下单');
  });

  it('renders risk settings without direction and order columns', () => {
    const record: AnalysisRecordPayload = {
      analysis_report: {
        headline: {
          action: '市价单',
          direction: '做多',
          summary: '风险参数已记录。',
        },
        metrics: [],
        decision: {
          order_type: '市价单',
          risk_profile: 'balanced',
          signal_threshold: 40,
          terminal: { outcome: 'trade' },
        },
        evidence_tables: [],
        flows: [],
        probability_blocks: [],
        lists: [],
      },
    };

    const html = renderToStaticMarkup(createElement(AnalysisReportPanel, { record }));

    expect(html).toContain('风险档位');
    expect(html).toContain('信号门槛');
    expect(html).toContain('均衡');
    expect(html).not.toContain('订单类型');
    expect(html).not.toContain('做多');
  });
});
