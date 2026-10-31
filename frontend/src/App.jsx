import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import ApprovalQueue from './pages/ApprovalQueue';
import ConnectedPages from './pages/ConnectedPages';
import PostMonitor from './pages/PostMonitor';
import RulesManager from './pages/RulesManager';
import AuditLogs from './pages/AuditLogs';
import Simulator from './pages/Simulator';
import Login from './pages/Login';
import AdsManager from './pages/AdsManager';
import ContentAutomation from './pages/ContentAutomation';
import api, { setAccessToken } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [metrics, setMetrics] = useState(null);
  const [simulationMode, setSimulationMode] = useState(true);
  const [liveModeReady, setLiveModeReady] = useState(false);
  const [liveModeBlockers, setLiveModeBlockers] = useState([]);
  const [accessToken, setAccessTokenState] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const fetchSimulationMode = async () => {
    try {
      const response = await api.get('/system/simulation-mode');
      setSimulationMode(response.data.simulation_mode);
      setLiveModeReady(response.data.live_ready);
      setLiveModeBlockers(response.data.live_blockers || []);
    } catch (err) {
      console.error('Failed to fetch simulation mode:', err);
    }
  };

  const handleSimulationModeChanged = (state) => {
    setSimulationMode(state.simulation_mode);
    setLiveModeReady(state.live_ready);
    setLiveModeBlockers(state.live_blockers || []);
  };

  const fetchMetrics = async () => {
    try {
      const res = await api.get('/reports/metrics');
      setMetrics(res.data);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  };

  useEffect(() => {
    let active = true;
    const handleAuthExpired = () => {
      setAccessToken(null);
      setAccessTokenState(null);
      setMetrics(null);
    };

    window.addEventListener('auth:expired', handleAuthExpired);
    api.post('/auth/refresh')
      .then((response) => {
        if (active) {
          setAccessToken(response.data.access_token);
          setAccessTokenState(response.data.access_token);
          void fetchMetrics();
          void fetchSimulationMode();
        }
      })
      .catch(() => {
        if (active) {
          setAccessToken(null);
          setAccessTokenState(null);
        }
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });

    return () => {
      active = false;
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, []);

  useEffect(() => {
    if (!accessToken) {
      return undefined;
    }

    const interval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(interval);
  }, [accessToken]);

  const handleLogin = (token) => {
    setAccessToken(token);
    setAccessTokenState(token);
    void fetchMetrics();
    void fetchSimulationMode();
  };

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error('Failed to revoke authentication session:', error);
    } finally {
      setAccessToken(null);
      setAccessTokenState(null);
      setMetrics(null);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-sm text-slate-500">
        Checking sign-in…
      </div>
    );
  }

  if (!accessToken) return <Login onLogin={handleLogin} />;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      <Navbar
        metrics={metrics}
        simulationMode={simulationMode}
        liveModeReady={liveModeReady}
        liveModeBlockers={liveModeBlockers}
        onSimulationModeChanged={handleSimulationModeChanged}
        onRefresh={fetchMetrics}
        onLogout={handleLogout}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          pendingCount={metrics?.pending_approvals_count || 0}
        />

        <main className="flex-1 p-8 overflow-y-auto max-h-[calc(100vh-65px)]">
          <div className="max-w-6xl mx-auto">
            {activeTab === 'dashboard' && (
              <Dashboard
                metrics={metrics}
                onNavigate={setActiveTab}
                onSimulateQuick={() => setActiveTab('simulator')}
              />
            )}
            {activeTab === 'queue' && (
              <ApprovalQueue onQueueUpdated={fetchMetrics} />
            )}
            {activeTab === 'pages' && (
              <ConnectedPages onPagesUpdated={fetchMetrics} />
            )}
            {activeTab === 'posts' && <PostMonitor onNavigate={setActiveTab} />}
            {activeTab === 'content' && <ContentAutomation simulationMode={simulationMode} />}
            {activeTab === 'ads' && <AdsManager />}
            {activeTab === 'rules' && <RulesManager />}
            {activeTab === 'logs' && <AuditLogs />}
            {activeTab === 'simulator' && (
              <Simulator
                onCommentSimulated={fetchMetrics}
                onNavigate={setActiveTab}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
