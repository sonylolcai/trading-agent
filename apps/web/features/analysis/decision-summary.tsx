import { StatusChip } from '../../components/status-chip';
import type { AnalysisDecision } from '../../types/api';
import { useI18n } from '../../lib/i18n/context';

function readDecisionBody(decision?: AnalysisDecision): Record<string, unknown> | undefined {
  if (!decision) {
    return undefined;
  }
  const nested = decision.decision;
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    return { ...decision, ...nested };
  }
  return decision;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  return String(value);
}

function metric(label: string, value: unknown) {
  return (
    <div className="metrics-grid__item" style={{ border: '1px solid var(--line-soft)', background: '#0c1215', padding: 8 }}>
      <span>{label}</span>
      <strong>{formatValue(value)}</strong>
    </div>
  );
}

export function DecisionSummary({ decision }: { decision?: AnalysisDecision }) {
  const { locale, translateLabel, translateValue } = useI18n();
  if (!decision) {
    return <div className="empty-state">{locale === 'zh' ? '暂未返回阶段二决策。' : 'No Stage 2 decision returned yet.'}</div>;
  }

  const body = readDecisionBody(decision);
  const action = body?.action ?? body?.order_type ?? 'decision';
  const direction = body?.direction ?? body?.order_direction;
  const confidence = body?.confidence ?? body?.trade_confidence;

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <div className="toolbar" style={{ justifyContent: 'flex-start' }}>
        <StatusChip tone={action === 'wait' || action === 'hold' ? 'warn' : 'info'}>{translateValue(formatValue(action))}</StatusChip>
        <StatusChip tone={direction ? 'good' : 'neutral'}>{direction ? translateValue(formatValue(direction)) : 'n/a'}</StatusChip>
        <StatusChip tone="info">{locale === 'zh' ? '置信度' : 'confidence'} {formatValue(confidence)}</StatusChip>
      </div>
      <div className="metrics-grid">
        {metric(translateLabel('Entry'), body?.entry ?? body?.entry_price)}
        {metric(translateLabel('Take profit'), body?.take_profit ?? body?.take_profit_price)}
        {metric(translateLabel('Stop loss'), body?.stop_loss ?? body?.stop_loss_price)}
        {metric(translateLabel('Order type'), body?.order_type ? translateValue(String(body.order_type)) : 'n/a')}
      </div>
      {body?.reasoning ? (
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--muted)', fontFamily: 'var(--mono)', fontSize: 12 }}>
          {formatValue(body.reasoning)}
        </pre>
      ) : null}
    </div>
  );
}

export function DecisionStatsBasis({ decision }: { decision?: AnalysisDecision }) {
  const { translateLabel } = useI18n();
  const body = readDecisionBody(decision);
  return (
    <div className="metrics-grid">
      {metric(translateLabel('Win-rate basis'), body?.estimated_win_rate_basis)}
      {metric(translateLabel('Sample count'), body?.historical_sample_count)}
      {metric(translateLabel('Win rate'), body?.historical_win_rate_for_this_setup)}
      {metric(translateLabel('Expectancy R'), body?.historical_expectancy_r)}
    </div>
  );
}
