import type { AnalysisDecision, AnalysisRecordPayload, AnalysisReport, AnalysisReportTone } from '../../types/api';

export type ReportMetricModel = {
  label: string;
  value: string;
  tone: AnalysisReportTone;
};

export type ReportFieldModel = {
  label: string;
  value: string;
  tone: AnalysisReportTone;
};

export type ReportEvidenceRowModel = {
  node: string;
  section: string;
  question: string;
  answer: string;
  basis: string;
  reason: string;
  skipped: boolean;
};

export type ReportEvidenceTableModel = {
  title: string;
  rows: ReportEvidenceRowModel[];
};

export type ReportFlowItemModel = {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: AnalysisReportTone;
};

export type ReportFlowModel = {
  title: string;
  items: ReportFlowItemModel[];
};

export type ReportProbabilityItemModel = {
  label: string;
  value: number;
  tone: AnalysisReportTone;
};

export type ReportProbabilityBlockModel = {
  title: string;
  items: ReportProbabilityItemModel[];
  reasoning: string;
};

export type ReportListModel = {
  title: string;
  items: string[];
};

export type ReportDecisionTreeNodeModel = {
  id: string;
  phase: string;
  question: string;
  answer: string;
  basis: string;
  reason: string;
  skipped: boolean;
  tone: AnalysisReportTone;
};

export type ReportDecisionTreeTerminalModel = {
  node: string;
  outcome: string;
  label: string;
  tone: AnalysisReportTone;
};

export type ReportDecisionTreeModel = {
  nodes: ReportDecisionTreeNodeModel[];
  terminal: ReportDecisionTreeTerminalModel | null;
};

export type AnalysisReportModel = {
  headline: {
    action: string;
    direction: string;
    summary: string;
    risk: string;
  };
  metrics: ReportMetricModel[];
  decisionFields: ReportFieldModel[];
  evidenceTables: ReportEvidenceTableModel[];
  flows: ReportFlowModel[];
  probabilityBlocks: ReportProbabilityBlockModel[];
  lists: ReportListModel[];
  decisionTree: ReportDecisionTreeModel;
  hasContent: boolean;
};

const EMPTY_HEADLINE = {
  action: 'pending',
  direction: 'n/a',
  summary: 'No analysis report returned yet.',
  risk: '',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function isNonEmpty(value: unknown): boolean {
  return value !== null && value !== undefined && value !== '';
}

function toRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function toText(value: unknown, fallback = 'n/a'): string {
  if (!isNonEmpty(value)) {
    return fallback;
  }
  return formatReportValue(value);
}

function readDecisionBody(decision?: AnalysisDecision | null): Record<string, unknown> {
  if (!decision) {
    return {};
  }
  const nested = decision.decision;
  if (isRecord(nested)) {
    return { ...decision, ...nested };
  }
  return decision;
}

function readNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.replace('%', '').trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function toneFromValue(value: unknown): AnalysisReportTone {
  const text = String(value ?? '').toLowerCase();
  if (text.includes('bad') || text.includes('bear') || text.includes('short') || text.includes('risk') || text.includes('weak')) {
    return 'bad';
  }
  if (text.includes('warn') || text.includes('wait') || text.includes('neutral') || text.includes('pending')) {
    return 'warn';
  }
  if (text.includes('good') || text.includes('bull') || text.includes('long') || text.includes('trade') || text.includes('strong')) {
    return 'good';
  }
  return 'info';
}

function metricTone(value: unknown, fallback: AnalysisReportTone = 'neutral'): AnalysisReportTone {
  const numeric = readNumber(value);
  if (numeric === null) {
    return fallback;
  }
  if (numeric >= 70) {
    return 'good';
  }
  if (numeric >= 45) {
    return 'warn';
  }
  return 'bad';
}

function formatMetricValue(value: unknown, unit?: string): string {
  const base = formatReportValue(value);
  if (!unit || base === 'n/a') {
    return base;
  }
  return `${base}${unit}`;
}

function percentMetric(value: unknown): string {
  if (!isNonEmpty(value)) {
    return 'n/a';
  }
  const text = String(value);
  return text.includes('%') ? text : `${formatReportValue(value)}%`;
}

function normalizeEvidenceRows(rows: unknown): ReportEvidenceRowModel[] {
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.filter(isRecord).map((row) => ({
    node: toText(row.node_id),
    section: toText(row.section, ''),
    question: toText(row.question, ''),
    answer: toText(row.answer, ''),
    basis: toText(row.bar_range, ''),
    reason: toText(row.reason, ''),
    skipped: row.skipped === true,
  }));
}

function normalizeEvidenceTable(title: string, rows: unknown): ReportEvidenceTableModel | null {
  const normalizedRows = normalizeEvidenceRows(rows);
  if (normalizedRows.length === 0) {
    return null;
  }
  return { title, rows: normalizedRows };
}

function normalizeFlowTone(value: unknown): AnalysisReportTone {
  const tone = String(value ?? '').toLowerCase();
  if (tone === 'good' || tone === 'warn' || tone === 'bad' || tone === 'info' || tone === 'neutral') {
    return tone;
  }
  return toneFromValue(value);
}

function traceTone(row: ReportEvidenceRowModel): AnalysisReportTone {
  if (row.skipped) {
    return 'neutral';
  }
  const text = `${row.answer} ${row.reason}`.toLowerCase();
  if (text.includes('yes') || text.includes('是') || text.includes('trade') || text.includes('long') || text.includes('bull')) {
    return 'good';
  }
  if (text.includes('no') || text.includes('否') || text.includes('reject') || text.includes('bear') || text.includes('risk')) {
    return 'bad';
  }
  if (text.includes('wait') || text.includes('hold') || text.includes('neutral') || text.includes('等待') || text.includes('中性')) {
    return 'warn';
  }
  return 'info';
}

function terminalTone(terminal: Record<string, unknown>): AnalysisReportTone {
  const outcome = String(terminal.outcome ?? terminal.label ?? '').toLowerCase();
  if (outcome.includes('trade') || outcome.includes('proceed')) {
    return 'good';
  }
  if (outcome.includes('reject')) {
    return 'bad';
  }
  if (outcome.includes('wait') || outcome.includes('hold')) {
    return 'warn';
  }
  return 'info';
}

function normalizeTerminal(value: unknown): ReportDecisionTreeTerminalModel | null {
  if (!isRecord(value) || Object.keys(value).length === 0) {
    return null;
  }
  return {
    node: toText(value.node_id ?? value.node, ''),
    outcome: toText(value.outcome, ''),
    label: toText(value.label, ''),
    tone: terminalTone(value),
  };
}

function buildDecisionTree(
  tables: ReportEvidenceTableModel[],
  terminal: unknown,
): ReportDecisionTreeModel {
  const nodes = tables.flatMap((table) =>
    table.rows.map((row) => ({
      id: row.node,
      phase: table.title,
      question: row.question,
      answer: row.answer,
      basis: row.basis,
      reason: row.reason,
      skipped: row.skipped,
      tone: traceTone(row),
    })),
  );

  return {
    nodes,
    terminal: normalizeTerminal(terminal),
  };
}

function normalizeProbabilityItems(source: unknown): ReportProbabilityItemModel[] {
  if (Array.isArray(source)) {
    return source
      .filter(isRecord)
      .map((item) => {
        const value = readNumber(item.value);
        return value === null
          ? null
          : {
              label: toText(item.label),
              value: clampPercent(value),
              tone: toneFromValue(item.label),
            };
      })
      .filter((item): item is ReportProbabilityItemModel => Boolean(item));
  }

  if (!isRecord(source)) {
    return [];
  }

  return Object.entries(source)
    .map(([label, value]) => {
      const numeric = readNumber(value);
      return numeric === null
        ? null
        : {
            label,
            value: clampPercent(numeric),
            tone: toneFromValue(label),
          };
    })
    .filter((item): item is ReportProbabilityItemModel => Boolean(item));
}

function listFromValues(title: string, values: unknown[]): ReportListModel | null {
  const items = values.flatMap((value) => {
    if (Array.isArray(value)) {
      return value.map(formatReportValue);
    }
    return isNonEmpty(value) ? [formatReportValue(value)] : [];
  }).filter((item) => item !== 'n/a');
  return items.length > 0 ? { title, items } : null;
}

function compact<T>(items: Array<T | null>): T[] {
  return items.filter((item): item is T => Boolean(item));
}

export function formatReportValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (Array.isArray(value)) {
    const parts = value.map(formatReportValue).filter((item) => item !== 'n/a');
    return parts.length > 0 ? parts.join(' / ') : 'n/a';
  }
  if (isRecord(value)) {
    const parts = Object.entries(value)
      .filter(([, item]) => isNonEmpty(item))
      .map(([key, item]) => `${key}: ${formatReportValue(item)}`);
    return parts.length > 0 ? parts.join(' / ') : 'n/a';
  }
  return String(value);
}

export function buildAnalysisReportModel(report?: AnalysisReport | null): AnalysisReportModel {
  if (!report) {
    return {
      headline: EMPTY_HEADLINE,
      metrics: [],
      decisionFields: [],
      evidenceTables: [],
      flows: [],
      probabilityBlocks: [],
      lists: [],
      decisionTree: { nodes: [], terminal: null },
      hasContent: false,
    };
  }

  const decision = report.decision ?? {};
  const evidenceTables = report.evidence_tables
    .map((table) => normalizeEvidenceTable(table.title, table.rows))
    .filter((table): table is ReportEvidenceTableModel => Boolean(table));
  const flows = report.flows
    .map((flow) => ({
      title: flow.title,
      items: flow.items.map((item) => ({
        id: toText(item.id),
        label: toText(item.label, ''),
        value: toText(item.value, ''),
        detail: toText(item.detail, ''),
        tone: normalizeFlowTone(item.tone ?? item.value ?? item.label),
      })),
    }))
    .filter((flow) => flow.items.length > 0);
  const probabilityBlocks = report.probability_blocks
    .map((block) => ({
      title: block.title,
      items: normalizeProbabilityItems(block.items),
      reasoning: toText(block.reasoning, ''),
    }))
    .filter((block) => block.items.length > 0);
  const lists = report.lists
    .map((list) => ({ title: list.title, items: list.items.map(formatReportValue).filter((item) => item !== 'n/a') }))
    .filter((list) => list.items.length > 0);
  const decisionTree = buildDecisionTree(evidenceTables, decision.terminal);

  return {
    headline: {
      action: toText(report.headline?.action),
      direction: 'n/a',
      summary: toText(report.headline?.summary, ''),
      risk: toText(report.headline?.risk, ''),
    },
    metrics: report.metrics.map((metric) => ({
      label: metric.label,
      value: formatMetricValue(metric.value, metric.unit),
      tone: metric.tone ?? metricTone(metric.value),
    })),
    decisionFields: [
      { label: 'Risk profile', value: toText(decision.risk_profile), tone: 'info' },
      { label: 'Signal threshold', value: toText(decision.signal_threshold), tone: 'info' },
      { label: 'Entry', value: toText(decision.entry_price), tone: 'info' },
      { label: 'Stop loss', value: toText(decision.stop_loss_price), tone: 'bad' },
      { label: 'Take profit', value: toText(decision.take_profit_price), tone: 'good' },
      { label: 'Terminal', value: toText(decision.terminal), tone: toneFromValue(decision.terminal) },
    ],
    evidenceTables,
    flows,
    probabilityBlocks,
    lists,
    decisionTree,
    hasContent: true,
  };
}

function fallbackMetrics(stage1: Record<string, unknown>, decision: Record<string, unknown>): ReportMetricModel[] {
  return compact([
    isNonEmpty(decision.trade_confidence ?? decision.confidence)
      ? {
          label: 'Trade confidence',
          value: percentMetric(decision.trade_confidence ?? decision.confidence),
          tone: metricTone(decision.trade_confidence ?? decision.confidence),
        }
      : null,
    isNonEmpty(decision.diagnosis_confidence ?? stage1.diagnosis_confidence)
      ? {
          label: 'Diagnosis confidence',
          value: percentMetric(decision.diagnosis_confidence ?? stage1.diagnosis_confidence),
          tone: metricTone(decision.diagnosis_confidence ?? stage1.diagnosis_confidence),
        }
      : null,
    isNonEmpty(decision.estimated_win_rate ?? decision.historical_win_rate_for_this_setup)
      ? {
          label: 'Win rate',
          value: percentMetric(decision.estimated_win_rate ?? decision.historical_win_rate_for_this_setup),
          tone: metricTone(decision.estimated_win_rate ?? decision.historical_win_rate_for_this_setup),
        }
      : null,
    isNonEmpty(decision.historical_sample_count)
      ? { label: 'Samples', value: formatReportValue(decision.historical_sample_count), tone: 'info' }
      : null,
    isNonEmpty(decision.historical_expectancy_r)
      ? { label: 'Expectancy R', value: formatReportValue(decision.historical_expectancy_r), tone: metricTone(decision.historical_expectancy_r, 'info') }
      : null,
  ]);
}

function fallbackDecisionFields(
  decision: Record<string, unknown>,
  stage2: Record<string, unknown>,
  record?: AnalysisRecordPayload | null,
): ReportFieldModel[] {
  return [
    { label: 'Risk profile', value: toText(decision.risk_profile ?? record?.decision_stance), tone: 'info' },
    { label: 'Signal threshold', value: toText(decision.signal_threshold ?? record?.decision_confidence_threshold), tone: 'info' },
    { label: 'Entry', value: toText(decision.entry_price ?? decision.entry), tone: 'info' },
    { label: 'Stop loss', value: toText(decision.stop_loss_price ?? decision.stop_loss), tone: 'bad' },
    { label: 'Take profit', value: toText(decision.take_profit_price ?? decision.take_profit), tone: 'good' },
    { label: 'Terminal', value: toText(stage2.terminal), tone: toneFromValue(stage2.terminal) },
  ];
}

function fallbackEvidenceTables(stage1: Record<string, unknown>, stage2: Record<string, unknown>): ReportEvidenceTableModel[] {
  return compact([
    normalizeEvidenceTable('Decision trace', stage2.decision_trace),
    normalizeEvidenceTable('Diagnostic gate', stage1.gate_trace),
  ]);
}

function fallbackFlows(stage1: Record<string, unknown>): ReportFlowModel[] {
  const rows = stage1.bar_by_bar_summary;
  if (!Array.isArray(rows)) {
    return [];
  }

  const items = rows.filter(isRecord).map((row, index) => {
    const context = toText(row.context_effect, '');
    const reason = toText(row.reason, '');
    const detail = [context, reason].filter(Boolean).join(' / ');
    return {
      id: toText(row.bar, `K${index + 1}`),
      label: toText(row.role, ''),
      value: toText(row.bar_type, ''),
      detail,
      tone: toneFromValue(row.context_effect ?? row.bar_type ?? row.role),
    };
  });

  return items.length > 0 ? [{ title: 'Bar-by-bar flow', items }] : [];
}

function probabilityBlock(title: string, prediction: unknown): ReportProbabilityBlockModel | null {
  if (!isRecord(prediction)) {
    return null;
  }
  const items = normalizeProbabilityItems(prediction.probabilities);
  if (items.length === 0) {
    return null;
  }
  return {
    title,
    items,
    reasoning: toText(prediction.reasoning, ''),
  };
}

function fallbackProbabilityBlocks(stage2: Record<string, unknown>): ReportProbabilityBlockModel[] {
  return compact([
    probabilityBlock('Next bar prediction', stage2.next_bar_prediction),
    probabilityBlock('Next cycle prediction', stage2.next_cycle_prediction),
  ]);
}

function fallbackLists(stage1: Record<string, unknown>, decision: Record<string, unknown>): ReportListModel[] {
  return compact([
    listFromValues('Key factors', [decision.key_factors]),
    listFromValues('Watch points', [decision.watch_points]),
    listFromValues('Observed signals', [stage1.key_signals, stage1.detected_patterns]),
  ]);
}

export function reportFromAnalysisRecord(record?: AnalysisRecordPayload | null, topLevelReport?: AnalysisReport | null): AnalysisReportModel {
  const explicitReport = topLevelReport ?? record?.analysis_report;
  if (explicitReport) {
    return buildAnalysisReportModel(explicitReport);
  }

  const stage1 = toRecord(record?.stage1_diagnosis);
  const stage2 = toRecord(record?.stage2_decision);
  const decision = readDecisionBody(record?.stage2_decision);
  const summaryParts = [
    isNonEmpty(stage1.cycle_position) ? `Cycle: ${formatReportValue(stage1.cycle_position)}` : '',
    isNonEmpty(decision.reasoning) ? formatReportValue(decision.reasoning) : '',
  ].filter(Boolean);
  const metrics = fallbackMetrics(stage1, decision);
  const evidenceTables = fallbackEvidenceTables(stage1, stage2);
  const flows = fallbackFlows(stage1);
  const probabilityBlocks = fallbackProbabilityBlocks(stage2);
  const lists = fallbackLists(stage1, decision);
  const decisionTree = buildDecisionTree(evidenceTables, stage2.terminal ?? decision.terminal);
  const hasContent =
    Object.keys(stage1).length > 0 ||
    Object.keys(stage2).length > 0 ||
    Object.keys(decision).length > 0 ||
    metrics.length > 0 ||
    evidenceTables.length > 0 ||
    flows.length > 0 ||
    probabilityBlocks.length > 0 ||
    lists.length > 0;

  if (!hasContent) {
    return buildAnalysisReportModel(null);
  }

  return {
    headline: {
      action: toText(decision.action ?? decision.order_type, 'decision'),
      direction: 'n/a',
      summary: summaryParts.join(' / '),
      risk: toText(decision.risk_assessment ?? stage1.risk_warning, ''),
    },
    metrics,
    decisionFields: fallbackDecisionFields(decision, stage2, record),
    evidenceTables,
    flows,
    probabilityBlocks,
    lists,
    decisionTree,
    hasContent,
  };
}
