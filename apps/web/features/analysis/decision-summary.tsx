import { StatusChip } from '../../components/status-chip';
import type { AnalysisDecision } from '../../types/api';

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
  if (!decision) {
    return <div className="empty-state">No Stage 2 decision returned yet.</div>;
  }

  const body = readDecisionBody(decision);
  const action = body?.action ?? body?.order_type ?? 'decision';
  const direction = body?.direction ?? body?.order_direction;
  const confidence = body?.confidence ?? body?.trade_confidence;

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <div className="toolbar" style={{ justifyContent: 'flex-start' }}>
        <StatusChip tone={action === 'wait' || action === 'hold' ? 'warn' : 'info'}>{formatValue(action)}</StatusChip>
        <StatusChip tone={direction ? 'good' : 'neutral'}>{formatValue(direction)}</StatusChip>
        <StatusChip tone="info">confidence {formatValue(confidence)}</StatusChip>
      </div>
      <div className="metrics-grid">
        {metric('Entry', body?.entry ?? body?.entry_price)}
        {metric('Take profit', body?.take_profit ?? body?.take_profit_price)}
        {metric('Stop loss', body?.stop_loss ?? body?.stop_loss_price)}
        {metric('Order type', body?.order_type)}
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
  const body = readDecisionBody(decision);
  return (
    <div className="metrics-grid">
      {metric('Win-rate basis', body?.estimated_win_rate_basis)}
      {metric('Sample count', body?.historical_sample_count)}
      {metric('Win rate', body?.historical_win_rate_for_this_setup)}
      {metric('Expectancy R', body?.historical_expectancy_r)}
    </div>
  );
}
