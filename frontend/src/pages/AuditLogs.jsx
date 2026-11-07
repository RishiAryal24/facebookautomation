import React, { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle2, XCircle, Clock } from 'lucide-react';
import api from '../api';

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const url = statusFilter ? `/reports/logs?status=${statusFilter}` : '/reports/logs';
      const res = await api.get(url);
      setLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [statusFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">
            Audit Logs &amp; Activity Reports
          </h1>
          <p className="mt-0.5 text-sm text-[#5b6475]">
            Historical trail of automated actions, publishing events and system errors (ANNEX A §2.7).
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="min-h-[40px] rounded-[10px] border border-[#d5d9e6] bg-white px-3 text-xs font-semibold text-[#141a2e]"
          >
            <option value="">All statuses</option>
            <option value="success">Success only</option>
            <option value="failed">Failed only</option>
            <option value="pending">Pending only</option>
          </select>

          <button
            onClick={fetchLogs}
            disabled={loading}
            className="min-h-[40px] px-4 rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] text-[#141a2e] text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      {/* Table Card */}
      <div className="bg-white rounded-2xl border border-[#e4e7ef] p-4 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs font-semibold text-[#5b6475] border-b border-[#eceef5]">
                <th className="pb-3 px-3">Date / Time</th>
                <th className="pb-3 px-3">Action</th>
                <th className="pb-3 px-3">Status</th>
                <th className="pb-3 px-3">Event details</th>
                <th className="pb-3 px-3">Error / note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eceef5]">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-[#5b6475] text-xs">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-[#1b2140]" />
                    Loading action logs...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-[#5b6475] text-xs">
                    No activity logs found for the selected filter.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[#f4f5f9]/50">
                    <td className="py-3 px-3 text-[#5b6475] text-xs whitespace-nowrap font-mono">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-3 font-semibold text-[#141a2e] text-xs capitalize whitespace-nowrap">
                      {log.action_type.replaceAll('_', ' ')}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${
                          log.status === 'success'
                            ? 'bg-[#dff5ea] text-[#0b6b4a]'
                            : log.status === 'failed'
                            ? 'bg-[#fde4e4] text-[#a31f1f]'
                            : 'bg-[#ffe9c7] text-[#7a3f00]'
                        }`}
                      >
                        {log.status === 'success' && <CheckCircle2 className="w-3 h-3 text-[#0b6b4a]" />}
                        {log.status === 'failed' && <XCircle className="w-3 h-3 text-[#a31f1f]" />}
                        {log.status === 'pending' && <Clock className="w-3 h-3 text-[#7a3f00]" />}
                        {log.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-[#3a4358] max-w-md font-mono text-xs truncate">
                      {log.details ? JSON.stringify(log.details) : '—'}
                    </td>
                    <td className="py-3 px-3 text-xs max-w-xs truncate">
                      {log.error_message ? (
                        <span className="text-[#a31f1f]">{log.error_message}</span>
                      ) : (
                        <span className="text-[#5b6475]">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
