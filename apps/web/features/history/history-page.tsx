'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import type { RecordsResponse, RecordSummary } from '../../types/api';
import { AnalysisReportPanel } from '../analysis/analysis-report-panel';

type HistoryPageProps = {
  initialRecords?: RecordSummary[];
  initialOpenId?: string;
};

export function HistoryPage({ initialRecords, initialOpenId }: HistoryPageProps = {}) {
  const [records, setRecords] = useState<ApiResult<RecordsResponse> | null>(() =>
    initialRecords ? { ok: true, data: { items: initialRecords } } : null,
  );
  const [loading, setLoading] = useState(!initialRecords);
  const [openId, setOpenId] = useState(initialOpenId ?? initialRecords?.[0]?.id ?? '');

  async function load() {
    setLoading(true);
    const next = await api.records();
    setRecords(next);
    if (next.ok && next.data.items.length > 0) {
      setOpenId((current) => current || next.data.items[0].id);
    }
    setLoading(false);
  }

  useEffect(() => {
    if (!initialRecords) {
      void load();
    }
  }, [initialRecords]);

  const rows = useMemo(() => (records?.ok ? records.data.items : []), [records]);

  return (
    <AppShell title="History">
      <section className="panel">
        <div className="panel__header">
          <div>
            <h2>Analysis Records</h2>
            <p>{rows.length} records from the local pending store</p>
          </div>
          <div className="toolbar">
            <StatusChip tone={records?.ok ? 'good' : 'bad'}>{records?.ok ? 'ready' : 'offline'}</StatusChip>
            <button className="icon-button" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh records">
              <RefreshCw size={15} aria-hidden="true" />
              <span>{loading ? 'Loading' : 'Refresh'}</span>
            </button>
          </div>
        </div>
        {!records?.ok && records ? (
          <div className="error-block">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>{records.error}</span>
          </div>
        ) : null}
        {rows.length === 0 ? (
          <div className="empty-state">No analysis records returned.</div>
        ) : (
          <div className="history-list">
            {rows.map((record) => {
              const expanded = openId === record.id;
              return (
                <article className="history-record" key={record.id}>
                  <button
                    className="history-record__button"
                    type="button"
                    aria-expanded={expanded}
                    data-history-expanded={expanded}
                    onClick={() => setOpenId((current) => (current === record.id ? '' : record.id))}
                  >
                    {expanded ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                    <span className="history-record__main">
                      <strong>{record.symbol}</strong>
                      <span>{record.timeframe} · {record.bar_count} bars · {record.timestamp_local_iso}</span>
                    </span>
                    <span className="history-record__meta">
                      <span>{record.decision_stance || 'n/a'}</span>
                      <span>{record.decision_confidence_threshold ?? 'n/a'}</span>
                      <StatusChip tone={record.has_exception ? 'bad' : 'good'}>{record.has_exception ? 'error' : 'ok'}</StatusChip>
                    </span>
                  </button>
                  {expanded ? (
                    <div className="history-record__body">
                      <h3>完整分析报告</h3>
                      <AnalysisReportPanel record={record} report={record.analysis_report} />
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </AppShell>
  );
}
