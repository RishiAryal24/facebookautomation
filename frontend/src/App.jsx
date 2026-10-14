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
import api from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchMetrics = async () => {
    try {
      const res = await api.get('/reports/metrics');
      setMetrics(res.data);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    // Auto refresh metrics every 30 seconds
    const interval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      <Navbar metrics={metrics} onRefresh={fetchMetrics} />

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
            {activeTab === 'posts' && <PostMonitor />}
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
