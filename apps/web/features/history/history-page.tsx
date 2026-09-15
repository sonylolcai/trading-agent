'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Calendar,
  ChevronDown,
  ChevronRight,
  Filter,
  Layers,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import type { RecordsResponse, RecordSummary } from '../../types/api';
import { AnalysisReportPanel } from '../analysis/analysis-report-panel';
import { useI18n } from '../../lib/i18n/context';

type HistoryPageProps = {
  initialRecords?: RecordSummary[];
  initialOpenId?: string;
};

export function HistoryPage({ initialRecords, initialOpenId }: HistoryPageProps = {}) {
  const { locale, t, translateValue } = useI18n();
  const [records, setRecords] = useState<ApiResult<RecordsResponse> | null>(() =>
    initialRecords ? { ok: true, data: { items: initialRecords } } : null,
  );
  const [loading, setLoading] = useState(!initialRecords);
  const [openId, setOpenId] = useState(initialOpenId ?? initialRecords?.[0]?.id ?? '');
  const [searchTerm, setSearchTerm] = useState('');
  const [stanceFilter, setStanceFilter] = useState<string>('all');

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

  const allRows = useMemo(() => (records?.ok ? records.data.items : []), [records]);

  const filteredRows = useMemo(() => {
    return allRows.filter((r) => {
      const matchSearch =
        searchTerm === '' ||
        r.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        r.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (r.action && r.action.toLowerCase().includes(searchTerm.toLowerCase()));
      const matchStance = stanceFilter === 'all' || r.decision_stance === stanceFilter;
      return matchSearch && matchStance;
    });
  }, [allRows, searchTerm, stanceFilter]);

  const stanceOptions = [
    { value: 'all', label: t.historyAll },
    { value: 'conservative', label: locale === 'zh' ? '稳健' : 'Conservative' },
    { value: 'balanced', label: locale === 'zh' ? '均衡' : 'Balanced' },
    { value: 'aggressive', label: locale === 'zh' ? '进取' : 'Aggressive' },
  ];

  return (
    <AppShell title={t.navHistory}>
      <section className="panel history-panel">
        <div className="panel__header">
          <div>
            <h2>{t.historyTitle}</h2>
            <p>
              {filteredRows.length} / {allRows.length} {t.historySub}
            </p>
          </div>
          <div className="toolbar">
            <StatusChip tone={records?.ok ? 'good' : 'bad'}>{records?.ok ? 'ready' : 'offline'}</StatusChip>
            <button className="icon-button" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh records">
              <RefreshCw size={15} aria-hidden="true" />
              <span>{loading ? t.loading : t.refresh}</span>
            </button>
          </div>
        </div>

        {/* Search and Stance Filter Toolbar */}
        <div className="history-filter-bar">
          <div className="history-search-wrap">
            <Search size={14} className="text-muted" />
            <input
              type="text"
              placeholder={t.historySearchPlaceholder}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="history-search-input"
            />
          </div>
          <div className="history-stance-chips">
            <SlidersHorizontal size={13} className="text-muted" />
            {stanceOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`history-filter-chip ${stanceFilter === opt.value ? 'history-filter-chip--active' : ''}`}
                onClick={() => setStanceFilter(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {!records?.ok && records ? (
          <div className="error-block">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>{records.error}</span>
          </div>
        ) : null}

        {filteredRows.length === 0 ? (
          <div className="empty-state">
            {allRows.length === 0 ? t.historyEmpty : t.historyNoMatch}
          </div>
        ) : (
          <div className="history-list">
            {filteredRows.map((record) => {
              const expanded = openId === record.id;
              const stance = record.decision_stance || 'balanced';
              const isTrade = record.action && !record.action.includes('不下单') && !record.action.includes('wait');
              return (
                <article className={`history-record-card history-record-card--${stance}`} key={record.id}>
                  <button
                    className="history-record__button"
                    type="button"
                    aria-expanded={expanded}
                    data-history-expanded={expanded}
                    onClick={() => setOpenId((current) => (current === record.id ? '' : record.id))}
                  >
                    <div className="history-record__left">
                      {expanded ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                      <div className="history-record__main">
                        <div className="history-symbol-row">
                          <strong className="history-symbol">{record.symbol}</strong>
                          <span className="history-tf-badge">{record.timeframe}</span>
                          <span className={`history-action-badge ${isTrade ? 'history-action-badge--trade' : 'history-action-badge--wait'}`}>
                            {translateValue(record.action || '不下单')}
                          </span>
                        </div>
                        <span className="history-meta-sub">
                          <Calendar size={11} className="text-muted" />
                          <span>{record.bar_count} bars · {record.timestamp_local_iso}</span>
                        </span>
                      </div>
                    </div>
                    <div className="history-record__meta">
                      <span className={`stance-badge stance-badge--${stance}`}>{record.decision_stance || 'n/a'}</span>
                      <span className="conf-threshold-badge">
                        {t.historyThreshold}: <strong>{record.decision_confidence_threshold ?? 'n/a'}</strong>
                      </span>
                      <StatusChip tone={record.has_exception ? 'bad' : 'good'}>{record.has_exception ? 'error' : 'ok'}</StatusChip>
                    </div>
                  </button>
                  {expanded ? (
                    <div className="history-record__body">
                      <div className="history-report-header">
                        <h3>{t.historyFullReport}</h3>
                        <span className="record-id-chip">{record.id}</span>
                      </div>
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

