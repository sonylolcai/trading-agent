'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { AppShell } from '../../components/app-shell';
import { StatusChip } from '../../components/status-chip';
import { api, type ApiResult } from '../../lib/api';
import type { RecordsResponse } from '../../types/api';

export function HistoryPage() {
  const [records, setRecords] = useState<ApiResult<RecordsResponse> | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setRecords(await api.records());
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

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
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>TF</th>
                  <th>Bars</th>
                  <th>Stance</th>
                  <th>Action</th>
                  <th>Direction</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((record) => (
                  <tr key={record.id}>
                    <td>{record.timestamp_local_iso}</td>
                    <td>{record.symbol}</td>
                    <td>{record.timeframe}</td>
                    <td>{record.bar_count}</td>
                    <td>{record.decision_stance || 'n/a'}</td>
                    <td>{record.action || 'n/a'}</td>
                    <td>{record.direction || 'n/a'}</td>
                    <td><StatusChip tone={record.has_exception ? 'bad' : 'good'}>{record.has_exception ? 'error' : 'ok'}</StatusChip></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
