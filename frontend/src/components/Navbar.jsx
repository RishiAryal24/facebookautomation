import React, { useState } from 'react';
import { Power, RefreshCw, LogOut, FlaskConical } from 'lucide-react';
import api from '../api';

export default function Navbar({
  metrics,
  simulationMode,
  liveModeReady,
  liveModeBlockers = [],
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
    <header className="bg-white border-b border-[#e4e7ef] sticky top-0 z-30 px-6 py-2.5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-[#f4f5f9] text-[#1b2140] border border-[#e4e7ef]">
          Bilingual AI Engagement · English &amp; नेपाली
        </span>
      </div>

      <div className="flex items-center gap-2.5">
        {/* Simulation Mode Pill Toggle */}
        <div className="flex flex-col items-end">
          <button
            type="button"
            onClick={handleToggleSimulation}
            disabled={changingMode || (simulationMode && !liveModeReady)}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              simulationMode
                ? 'bg-white border-[#e4e7ef] text-[#5b6475] hover:text-[#141a2e] hover:border-slate-300'
                : 'bg-[#dff5ea] border-[#0b6b4a]/30 text-[#0b6b4a] font-semibold'
            }`}
            title={
              simulationMode && !liveModeReady
                ? liveModeBlockers.join(' ')
                : simulationMode
                  ? 'Click to switch to live Facebook mode'
                  : 'Click to switch to trial simulation'
            }
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>{simulationMode ? 'Simulation on · Trial' : 'Simulation off · Live'}</span>
          </button>
          {simulationMode && !liveModeReady && (
            <span className="mt-0.5 max-w-56 text-right text-[10px] text-[#5b6475]">
              Validate real Page before switching live.
            </span>
          )}
        </div>

        {/* Status Badge */}
        <span className="inline-flex items-center gap-2 bg-white border border-[#e4e7ef] rounded-full px-3.5 py-1.5 text-xs font-medium text-[#141a2e]">
          <span
            className={`w-2 h-2 rounded-full ${
              metrics?.automation_active ? 'bg-[#12875f]' : 'bg-[#a31f1f]'
            }`}
          />
          {metrics?.automation_active ? 'Automation active' : 'Automation paused'}
        </span>

        {/* Emergency Halt / Resume Button */}
        <button
          onClick={handleToggleEmergency}
          disabled={stopping}
          className={`flex items-center gap-1.5 px-4 min-h-[36px] rounded-[10px] text-xs font-semibold transition-all ${
            metrics?.automation_active
              ? 'bg-white border border-[#e9b8b8] text-[#a31f1f] hover:bg-[#fde4e4]'
              : 'bg-[#0b6b4a] border border-[#0b6b4a] text-white hover:bg-[#09573c]'
          }`}
          title={
            metrics?.automation_active
              ? 'Emergency Stop: Instantly halt all automations'
              : 'Resume Automations'
          }
        >
          <Power className="w-3.5 h-3.5" />
          <span>{metrics?.automation_active ? 'Emergency halt' : 'Resume automation'}</span>
        </button>

        {/* Refresh Data */}
        <button
          onClick={onRefresh}
          className="p-2 rounded-[10px] text-[#5b6475] hover:text-[#141a2e] hover:bg-[#eef0f6] transition-colors"
          title="Refresh Dashboard"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Sign out */}
        <button
          onClick={onLogout}
          className="p-2 rounded-[10px] text-[#5b6475] hover:text-[#a31f1f] hover:bg-[#fde4e4] transition-colors"
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
