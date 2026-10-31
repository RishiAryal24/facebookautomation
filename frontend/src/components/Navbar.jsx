import React, { useState } from 'react';
import { Power, RefreshCw, Sparkles, LogOut, FlaskConical } from 'lucide-react';
import api from '../api';

export default function Navbar({
  metrics,
  simulationMode,
  liveModeReady,
  liveModeBlockers,
  onSimulationModeChanged,
  onRefresh,
  onLogout,
}) {
  const [stopping, setStopping] = useState(false);
  const [changingMode, setChangingMode] = useState(false);

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

  const handleToggleSimulation = async () => {
    const nextMode = !simulationMode;
    if (!nextMode && !liveModeReady) return;
    const prompt = nextMode
      ? 'Turn simulation ON? Publishing will be disabled and trial data may be simulated.'
      : 'Turn simulation OFF? Publishing will use the validated Facebook Page and can create real posts.';
    if (!confirm(prompt)) return;

    setChangingMode(true);
    try {
      const response = await api.put('/system/simulation-mode', {
        simulation_mode: nextMode,
      });
      onSimulationModeChanged?.(response.data);
    } catch (err) {
      alert('Failed to change simulation mode: ' + err.message);
    } finally {
      setChangingMode(false);
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

      <div className="flex items-center space-x-3">
        <div className="flex flex-col items-end">
          <button
            type="button"
            onClick={handleToggleSimulation}
            disabled={changingMode || (simulationMode && !liveModeReady)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              simulationMode
                ? 'bg-amber-50 border-amber-300 text-amber-800 hover:bg-amber-100'
                : 'bg-emerald-50 border-emerald-300 text-emerald-800 hover:bg-emerald-100'
            }`}
            title={
              simulationMode && !liveModeReady
                ? liveModeBlockers.join(' ')
                : simulationMode
                  ? 'Turn simulation off for live Facebook operations'
                  : 'Turn simulation on for a trial run'
            }
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>{simulationMode ? 'Simulation ON' : 'Simulation OFF'}</span>
            <span aria-hidden="true">{simulationMode ? '→ Live' : '→ Trial'}</span>
          </button>
          {simulationMode && !liveModeReady && (
            <span className="mt-1 max-w-56 text-right text-[10px] text-slate-500">
              Validate the real Page before switching live.
            </span>
          )}
        </div>

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
        <button
          onClick={onLogout}
          className="p-2 rounded-lg text-slate-500 hover:text-rose-700 hover:bg-rose-50 transition-colors"
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
