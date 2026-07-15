'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Languages } from 'lucide-react';
import { StatusChip } from '../../components/status-chip';
import type { AnalysisRecordPayload, AnalysisReport } from '../../types/api';
import type {
  AnalysisReportModel,
  ReportDecisionTreeModel,
  ReportFlowModel,
  ReportListModel,
  ReportProbabilityBlockModel,
} from './analysis-report';
import { reportFromAnalysisRecord } from './analysis-report';
import { useI18n } from '../../lib/i18n/context';

type AnalysisReportPanelProps = {
  record?: AnalysisRecordPayload | null;
  report?: AnalysisReport | null;
};

function actionTone(action: string) {
  const text = action.toLowerCase();
  if (
    text.includes('wait') ||
    text.includes('hold') ||
    text.includes('no order') ||
    action.includes('不下单') ||
    action.includes('等待')
  ) {
    return 'warn';
  }
  return 'good';
}



function ReportMetricStrip({ model }: { model: AnalysisReportModel }) {
  const { translateLabel } = useI18n();
  if (model.metrics.length === 0) {
    return null;
  }
  return (
    <div className="analysis-report__metric-strip">
      {model.metrics.map((metric) => (
        <div className={`analysis-report__metric analysis-report__metric--${metric.tone}`} key={`${metric.label}-${metric.value}`}>
          <span>{translateLabel(metric.label)}</span>
          <strong>{metric.value}</strong>
        </div>
      ))}
    </div>
  );
}

function DecisionFields({ model }: { model: AnalysisReportModel }) {
  const { translateLabel, translateValue } = useI18n();
  const visibleFields = model.decisionFields.filter((field) => field.value !== 'n/a');
  if (visibleFields.length === 0) {
    return null;
  }
  return (
    <div className="analysis-report__decision-grid">
      {visibleFields.map((field) => (
        <div className={`analysis-report__field analysis-report__field--${field.tone}`} key={field.label}>
          <span>{translateLabel(field.label)}</span>
          <strong>{translateValue(field.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function CollapseToggle({
  expanded,
  onToggle,
}: {
  expanded: boolean;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  return (
    <button className="collapse-button" type="button" aria-expanded={expanded} onClick={onToggle}>
      {expanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
      <span>{expanded ? t.collapse : t.expand}</span>
    </button>
  );
}

function DecisionTreeView({ tree }: { tree: ReportDecisionTreeModel }) {
  const { t, translateLabel, translateValue } = useI18n();
  const [expanded, setExpanded] = useState(true);
  if (tree.nodes.length === 0 && !tree.terminal) {
    return null;
  }
  return (
    <section className="analysis-report__section">
      <div className="analysis-report__section-head">
        <h3>{t.decisionTree}</h3>
        <div className="analysis-report__section-actions">
          <StatusChip tone="info">{tree.nodes.length} {t.nodes}</StatusChip>
          <CollapseToggle expanded={expanded} onToggle={() => setExpanded((current) => !current)} />
        </div>
      </div>
      {expanded ? (
        <div className="analysis-report__decision-tree">
          {tree.nodes.map((node, index) => (
            <div className={`analysis-report__tree-node analysis-report__tree-node--${node.tone}`} key={`${node.id}-${index}`}>
              <div className="analysis-report__tree-index">{index + 1}</div>
              <div className="analysis-report__tree-branch" aria-hidden="true" />
              <div className="analysis-report__tree-card">
                <div className="analysis-report__tree-meta">
                  <span>{translateLabel(node.phase)}</span>
                  <strong>{node.id}</strong>
                </div>
                <h4>{node.question || node.id}</h4>
                <div className="analysis-report__tree-facts">
                  <span>{t.answer}: {translateValue(node.answer)}</span>
                  {node.basis ? <span>{t.basis}: {node.basis}</span> : null}
                </div>
                {node.reason ? <p>{node.reason}</p> : null}
              </div>
            </div>
          ))}
          {tree.terminal ? (
            <div className={`analysis-report__tree-terminal analysis-report__tree-terminal--${tree.terminal.tone}`}>
              <span>{t.terminal}{tree.terminal.node ? ` · ${tree.terminal.node}` : ''}</span>
              <strong>{translateValue(tree.terminal.outcome || tree.terminal.label)}</strong>
              {tree.terminal.label ? <p>{translateValue(tree.terminal.label)}</p> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function FlowTimeline({ flow }: { flow: ReportFlowModel }) {
  const { translateLabel, translateValue } = useI18n();
  return (
    <div className="analysis-report__timeline">
      {flow.items.map((item) => (
        <div className={`analysis-report__step analysis-report__step--${item.tone}`} key={item.id}>
          <div className="analysis-report__step-marker">{item.id}</div>
          <div className="analysis-report__step-body">
            <span>{translateLabel(item.label || 'bar')}</span>
            <strong>{translateValue(item.value || 'n/a')}</strong>
            {item.detail ? <p>{item.detail}</p> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function FlowSections({ flows }: { flows: ReportFlowModel[] }) {
  const { t, translateLabel } = useI18n();
  if (flows.length === 0) {
    return null;
  }
  return (
    <section className="analysis-report__section">
      <div className="analysis-report__section-head">
        <h3>{t.klineFlow}</h3>
        <StatusChip tone="neutral">K1-K8</StatusChip>
      </div>
      {flows.map((flow) => (
        <div className="analysis-report__flow" key={flow.title}>
          <div className="analysis-report__subhead">
            <h4>{translateLabel(flow.title)}</h4>
            <span>{flow.items.length} {t.bars}</span>
          </div>
          <FlowTimeline flow={flow} />
        </div>
      ))}
    </section>
  );
}

function ProbabilityBlock({ block }: { block: ReportProbabilityBlockModel }) {
  const { t, locale, translateLabel, explainProbability } = useI18n();
  return (
    <div className="analysis-report__probability-block">
      <div className="analysis-report__subhead">
        <h4>{translateLabel(block.title)}</h4>
        <span>{t.probability}</span>
      </div>
      <div className="analysis-report__probability-list">
        {block.items.map((item) => {
          const label = translateLabel(item.label);
          const explanation = explainProbability(item.label);
          return (
            <div className="analysis-report__probability" key={item.label}>
              <div className="analysis-report__probability-label">
                <span>
                  {label}
                  {locale === 'zh' && label !== item.label ? <small>{item.label}</small> : null}
                </span>
                <strong>{item.value}%</strong>
              </div>
              <div className="analysis-report__bar" aria-label={`${label} ${item.value}%`}>
                <span className={`analysis-report__bar-fill analysis-report__bar-fill--${item.tone}`} style={{ width: `${item.value}%` }} />
              </div>
              {explanation ? <p className="analysis-report__probability-help">{explanation}</p> : null}
            </div>
          );
        })}
      </div>
      {block.reasoning ? <p className="analysis-report__reasoning">{block.reasoning}</p> : null}
    </div>
  );
}

function ProbabilitySections({ blocks }: { blocks: ReportProbabilityBlockModel[] }) {
  const { t } = useI18n();
  if (blocks.length === 0) {
    return null;
  }
  return (
    <section className="analysis-report__section">
      <div className="analysis-report__section-head">
        <h3>{t.probabilityForecast}</h3>
        <StatusChip tone="info">{t.forecast}</StatusChip>
      </div>
      <div className="analysis-report__probability-grid">
        {blocks.map((block) => (
          <ProbabilityBlock block={block} key={block.title} />
        ))}
      </div>
    </section>
  );
}

function ListCard({ list }: { list: ReportListModel }) {
  const { translateLabel } = useI18n();
  return (
    <div className="analysis-report__list">
      <div className="analysis-report__subhead">
        <h4>{translateLabel(list.title)}</h4>
        <span>{list.items.length}</span>
      </div>
      <ul>
        {list.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function ListSections({ lists }: { lists: ReportListModel[] }) {
  const { t } = useI18n();
  if (lists.length === 0) {
    return null;
  }
  return (
    <section className="analysis-report__section">
      <div className="analysis-report__section-head">
        <h3>{t.keyFactors}</h3>
        <StatusChip tone="neutral">{t.observations}</StatusChip>
      </div>
      <div className="analysis-report__list-grid">
        {lists.map((list) => (
          <ListCard list={list} key={list.title} />
        ))}
      </div>
    </section>
  );
}

export function AnalysisReportPanel({ record, report }: AnalysisReportPanelProps) {
  const { t, translateValue } = useI18n();
  const model = reportFromAnalysisRecord(record, report);

  if (!model.hasContent) {
    return <div className="empty-state">{t.empty}</div>;
  }

  return (
    <div className="analysis-report">
      <section className="analysis-report__headline">
        <div className="analysis-report__headline-main">
          <div className="analysis-report__chips">
            <StatusChip tone={actionTone(model.headline.action)}>{translateValue(model.headline.action)}</StatusChip>
          </div>
          <h3>{model.headline.summary || t.structuredReport}</h3>
          {model.headline.risk ? <p>{model.headline.risk}</p> : null}
        </div>
        <ReportMetricStrip model={model} />
      </section>
      <DecisionFields model={model} />
      <ListSections lists={model.lists} />
      <DecisionTreeView tree={model.decisionTree} />
      <FlowSections flows={model.flows} />
      <ProbabilitySections blocks={model.probabilityBlocks} />
    </div>
  );
}
