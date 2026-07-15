import { describe, expect, it } from 'vitest';
import {
  buildAnalysisReportModel,
  formatReportValue,
  reportFromAnalysisRecord,
} from '../features/analysis/analysis-report';
import type { AnalysisRecordPayload, AnalysisReport } from '../types/api';

const directReport: AnalysisReport = {
  headline: {
    action: 'trade',
    direction: 'long',
    summary: 'Breakout continuation is active.',
    risk: 'Failed follow-through below K1.',
  },
  metrics: [
    { label: 'Trade confidence', value: 72, unit: '%', tone: 'good' },
    { label: 'Samples', value: 47, tone: 'info' },
  ],
  decision: {
    order_type: 'market',
    risk_profile: 'balanced',
    signal_threshold: 40,
    entry_price: 13.2,
    stop_loss_price: 12.6,
    take_profit_price: 15,
    terminal: { node_id: '10.3', outcome: 'trade', label: 'trigger' },
  },
  evidence_tables: [
    {
      title: 'Decision trace',
      rows: [
        {
          node_id: '10.3',
          question: 'Does K1 confirm breakout?',
          answer: 'yes',
          reason: 'K1 closes near high.',
          bar_range: 'K1',
        },
        {
          node_id: '10.4',
          question: 'Is pullback required?',
          answer: 'n/a',
          reason: 'Terminal already reached.',
          bar_range: 'K2-K1',
          skipped: true,
        },
      ],
    },
  ],
  flows: [
    {
      title: 'Bar flow',
      items: [
        { id: 'K1', label: 'signal', value: 'trend_bull', detail: 'Wide body', tone: 'good' },
      ],
    },
  ],
  probability_blocks: [
    {
      title: 'Next bar',
      items: [
        { label: 'bullish', value: 68 },
        { label: 'bearish', value: 14 },
      ],
      reasoning: 'Momentum remains intact.',
    },
  ],
  lists: [{ title: 'Key factors', items: ['K1 breakout', 'EMA support'] }],
};

describe('analysis report model helpers', () => {
  it('formats arrays and objects as readable text instead of JSON strings', () => {
    expect(formatReportValue(['K1 breakout', 'EMA support'])).toBe('K1 breakout / EMA support');
    expect(formatReportValue({ outcome: 'trade', node_id: '10.3' })).toBe('outcome: trade / node_id: 10.3');
    expect(formatReportValue({ nested: { raw: true } })).toBe('nested: raw: true');

    const model = buildAnalysisReportModel(directReport);
    const displayValues = [
      ...model.metrics.map((metric) => metric.value),
      ...model.decisionFields.map((field) => field.value),
      ...model.evidenceTables.flatMap((table) => table.rows.flatMap((row) => [row.node, row.question, row.answer, row.basis, row.reason])),
      ...model.flows.flatMap((flow) => flow.items.flatMap((item) => [item.id, item.label, item.value, item.detail])),
    ].join('\n');

    expect(displayValues).not.toContain('["K1 breakout"');
    expect(displayValues).not.toContain('{"outcome"');
  });

  it('normalizes trace rows into a decision path table model', () => {
    const model = buildAnalysisReportModel(directReport);

    expect(model.evidenceTables[0]).toMatchObject({
      title: 'Decision trace',
      rows: [
        {
          node: '10.3',
          question: 'Does K1 confirm breakout?',
          answer: 'yes',
          basis: 'K1',
          reason: 'K1 closes near high.',
          skipped: false,
        },
        {
          node: '10.4',
          question: 'Is pullback required?',
          answer: 'n/a',
          basis: 'K2-K1',
          reason: 'Terminal already reached.',
          skipped: true,
        },
      ],
    });
  });

  it('uses analysis_report directly for bar flow, probabilities, and list cards', () => {
    const model = buildAnalysisReportModel(directReport);

    expect(model.flows[0].items[0]).toMatchObject({
      id: 'K1',
      label: 'signal',
      value: 'trend_bull',
      detail: 'Wide body',
      tone: 'good',
    });
    expect(model.probabilityBlocks[0]).toMatchObject({
      title: 'Next bar',
      reasoning: 'Momentum remains intact.',
      items: [
        { label: 'bullish', value: 68 },
        { label: 'bearish', value: 14 },
      ],
    });
    expect(model.lists).toContainEqual({ title: 'Key factors', items: ['K1 breakout', 'EMA support'] });
  });

  it('shows risk profile fields instead of order and direction fields', () => {
    const model = buildAnalysisReportModel(directReport);

    expect(model.headline.direction).toBe('n/a');
    expect(model.decisionFields).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: 'Risk profile', value: 'balanced' }),
        expect.objectContaining({ label: 'Signal threshold', value: '40' }),
      ]),
    );
    expect(model.decisionFields.some((field) => field.label === 'Order type')).toBe(false);
  });

  it('builds a decision tree path from trace tables and terminal data', () => {
    const model = buildAnalysisReportModel(directReport);

    expect(model.decisionTree.nodes).toMatchObject([
      {
        id: '10.3',
        phase: 'Decision trace',
        question: 'Does K1 confirm breakout?',
        answer: 'yes',
        basis: 'K1',
        tone: 'good',
      },
      {
        id: '10.4',
        phase: 'Decision trace',
        answer: 'n/a',
        skipped: true,
        tone: 'neutral',
      },
    ]);
    expect(model.decisionTree.terminal).toMatchObject({
      node: '10.3',
      outcome: 'trade',
      label: 'trigger',
      tone: 'good',
    });
  });

  it('builds report sections from legacy stage1 and stage2 record fields when analysis_report is absent', () => {
    const legacyRecord: AnalysisRecordPayload = {
      stage1_diagnosis: {
        cycle_position: 'normal_channel',
        direction: 'bullish',
        diagnosis_confidence: 64,
        key_signals: ['EMA support', 'Higher low'],
        detected_patterns: ['two leg pullback'],
        risk_warning: 'Range high overhead.',
        bar_by_bar_summary: [
          {
            bar: 'K1',
            role: 'signal',
            bar_type: 'trend_bull',
            context_effect: 'strengthens_bull',
            follow_through: 'pending',
            reason: 'Strong close.',
          },
        ],
      },
      stage2_decision: {
        decision: {
          order_type: 'limit',
          order_direction: 'long',
          entry_price: 13.2,
          stop_loss_price: 12.6,
          take_profit_price: 15,
          trade_confidence: 58,
          estimated_win_rate: 61,
          key_factors: ['Fresh signal bar'],
          watch_points: ['K1 follow-through'],
          risk_assessment: 'Failed breakout risk.',
        },
        decision_trace: [
          {
            node_id: '10.1',
            question: 'Is setup fresh?',
            answer: 'yes',
            reason: 'Signal bar is K1.',
            bar_range: 'K1',
          },
        ],
        next_bar_prediction: {
          direction: 'bullish',
          probabilities: { bullish: 61, bearish: 19, neutral: 20 },
          reasoning: 'Signal bar favors continuation.',
          unpredictable: false,
          features_used: ['stage1_diagnosis'],
        },
      },
    };

    const model = reportFromAnalysisRecord(legacyRecord);

    expect(model.metrics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: 'Trade confidence', value: '58%' }),
        expect.objectContaining({ label: 'Diagnosis confidence', value: '64%' }),
        expect.objectContaining({ label: 'Win rate', value: '61%' }),
      ]),
    );
    expect(model.evidenceTables[0].rows[0]).toMatchObject({ node: '10.1', basis: 'K1' });
    expect(model.flows[0].items[0]).toMatchObject({
      id: 'K1',
      label: 'signal',
      value: 'trend_bull',
      detail: 'strengthens_bull / Strong close.',
    });
    expect(model.probabilityBlocks[0].items).toMatchObject([
      { label: 'bullish', value: 61 },
      { label: 'bearish', value: 19 },
      { label: 'neutral', value: 20 },
    ]);
    expect(model.lists).toEqual(
      expect.arrayContaining([
        { title: 'Key factors', items: ['Fresh signal bar'] },
        { title: 'Watch points', items: ['K1 follow-through'] },
        { title: 'Observed signals', items: ['EMA support', 'Higher low', 'two leg pullback'] },
      ]),
    );
  });
});
