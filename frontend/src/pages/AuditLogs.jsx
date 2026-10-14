import React, { useState, useEffect } from 'react';
import { FileText, RefreshCw, CheckCircle2, XCircle, Clock, Filter } from 'lucide-react';
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Audit Logs & Activity Reports</h2>
          <p className="text-xs text-slate-500 mt-1">
            Historical audit trail of all automated actions, publishing events, and system errors (ANNEX A §2.7).
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-700"
          >
            <option value="">All Statuses</option>
            <option value="success">Success Only</option>
            <option value="failed">Failed Only</option>
            <option value="pending">Pending Only</option>
          </select>

          <button
            onClick={fetchLogs}
            disabled={loading}
            className="px-3.5 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="p-3.5">Time</th>
                <th className="p-3.5">Action Type</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">Event Details</th>
                <th className="p-3.5">Error / Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                    Loading action logs...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-400">
                    No activity logs found for the selected filter.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70">
                    <td className="p-3.5 text-slate-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="p-3.5 font-bold text-slate-900 uppercase tracking-tight text-[11px]">
                      {log.action_type.replace('_', ' ')}
                    </td>
                    <td className="p-3.5">
                      <span className={`px-2 py-0.5 rounded-full font-semibold text-[11px] inline-flex items-center gap-1 ${
                        log.status === 'success'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : log.status === 'failed'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        {log.status === 'success' && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                        {log.status === 'failed' && <XCircle className="w-3 h-3 text-rose-600" />}
                        {log.status === 'pending' && <Clock className="w-3 h-3 text-amber-600" />}
                        {log.status}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-700 max-w-md font-mono text-[11px] truncate">
                      {log.details ? JSON.stringify(log.details) : '—'}
                    </td>
                    <td className="p-3.5 text-rose-600 text-[11px]">
                      {log.error_message || '—'}
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
