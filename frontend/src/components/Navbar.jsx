import React, { useState } from 'react';
import { ShieldAlert, ShieldCheck, Power, RefreshCw, Sparkles } from 'lucide-react';
import api from '../api';

export default function Navbar({ metrics, onRefresh }) {
  const [stopping, setStopping] = useState(false);

  const handleToggleEmergency = async () => {
    setStopping(true);
    try {
      if (metrics?.automation_active) {
        await api.post('/reports/emergency-stop');
      } else {
        await api.post('/reports/resume-all');
      }
      if (onRefresh) onRefresh();
    } catch (err) {
      alert('Action failed: ' + err.message);
    } finally {
      setStopping(false);
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between shadow-xs">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
          PL
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">PyLoom Automation</h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              v1.0 MoE
            </span>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> Bilingual Gemini AI
            </span>
          </div>
          <p className="text-xs text-slate-500">Facebook Page Engagement & Automation System (ANNEX A)</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Status Badge */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg border bg-slate-50 border-slate-200 text-xs">
          <span className={`w-2.5 h-2.5 rounded-full ${metrics?.automation_active ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
          <span className="font-medium text-slate-700">
            {metrics?.automation_active ? 'Automation Active' : 'Automation Paused'}
          </span>
        </div>

        {/* Global Emergency Kill Switch */}
        <button
          onClick={handleToggleEmergency}
          disabled={stopping}
          className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs ${
            metrics?.automation_active
              ? 'bg-rose-50 text-rose-700 border border-rose-300 hover:bg-rose-100 hover:text-rose-800'
              : 'bg-emerald-600 text-white hover:bg-emerald-700'
          }`}
          title={metrics?.automation_active ? "Emergency Stop: Instantly halt all automations" : "Resume Automations"}
        >
          <Power className="w-3.5 h-3.5" />
          <span>{metrics?.automation_active ? 'Emergency Halt' : 'Resume Automation'}</span>
        </button>

        {/* Refresh Data */}
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
          title="Refresh Dashboard"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
