import React from 'react';
import { 
  Globe2, 
  Newspaper, 
  MessageSquare, 
  Clock, 
  CheckCircle2, 
  Heart, 
  ArrowRight, 
  Play,
  ShieldCheck
} from 'lucide-react';

export default function Dashboard({ metrics, onNavigate, onSimulateQuick }) {
  const cards = [
    {
      title: 'Connected Pages',
      value: metrics?.total_pages_connected || 0,
      icon: Globe2,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
      border: 'border-blue-100',
      actionText: 'Manage Pages',
      tab: 'pages'
    },
    {
      title: 'Monitored Posts',
      value: metrics?.total_posts_monitored || 0,
      icon: Newspaper,
      color: 'text-indigo-600',
      bg: 'bg-indigo-50',
      border: 'border-indigo-100',
      actionText: 'View Feed',
      tab: 'posts'
    },
    {
      title: 'Comments Ingested',
      value: metrics?.total_comments_received || 0,
      icon: MessageSquare,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
      border: 'border-purple-100',
      actionText: 'View Posts',
      tab: 'posts'
    },
    {
      title: 'Pending Approvals',
      value: metrics?.pending_approvals_count || 0,
      icon: Clock,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      actionText: 'Triage Queue',
      tab: 'queue',
      highlight: (metrics?.pending_approvals_count || 0) > 0
    },
    {
      title: 'Published AI Replies',
      value: metrics?.published_replies_count || 0,
      icon: CheckCircle2,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      border: 'border-emerald-100',
      actionText: 'Audit Logs',
      tab: 'logs'
    },
    {
      title: 'Likes & Reactions',
      value: metrics?.total_likes_given || 0,
      icon: Heart,
      color: 'text-rose-600',
      bg: 'bg-rose-50',
      border: 'border-rose-100',
      actionText: 'Engagement Settings',
      tab: 'rules'
    },
  ];

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-blue-700 via-indigo-700 to-blue-800 rounded-2xl p-6 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <span className="px-2.5 py-1 bg-white/20 rounded-full text-xs font-semibold uppercase tracking-wider backdrop-blur-xs">
            PyLoom Facebook Automation Control Hub
          </span>
          <h2 className="text-2xl font-bold mt-2">Bilingual AI Engagement Engine</h2>
          <p className="text-blue-100 text-sm mt-1 max-w-xl">
            Autonomous & supervised Facebook comment response, policy-compliant reactions, and real-time sentiment analysis in English and Nepali.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigate('simulator')}
            className="px-4 py-2 bg-white text-blue-700 hover:bg-blue-50 font-semibold text-sm rounded-xl transition-all shadow-sm flex items-center gap-2"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Test Live Comment</span>
          </button>
          <button
            onClick={() => onNavigate('queue')}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white font-semibold text-sm rounded-xl transition-all shadow-sm flex items-center gap-2"
          >
            <Clock className="w-4 h-4" />
            <span>Review Queue ({metrics?.pending_approvals_count || 0})</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className={`bg-white rounded-2xl p-5 border transition-all hover:shadow-md ${card.border} ${
                card.highlight ? 'ring-2 ring-amber-400' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  {card.title}
                </span>
                <div className={`p-2.5 rounded-xl ${card.bg}`}>
                  <Icon className={`w-5 h-5 ${card.color}`} />
                </div>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-slate-900">{card.value}</span>
                <button
                  onClick={() => onNavigate(card.tab)}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1 group"
                >
                  <span>{card.actionText}</span>
                  <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Status & Recent Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Policy Guardrails Status Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 space-y-4">
          <div className="flex items-center space-x-2 text-slate-900 font-bold">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <span>Safety & Policy Guardrails</span>
          </div>
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <span className="text-slate-600 font-medium">Bilingual Support</span>
              <span className="font-semibold text-slate-900">English + नेपाली</span>
            </div>
            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <span className="text-slate-600 font-medium">Restricted Keyword Filter</span>
              <span className="font-semibold text-emerald-600">Active (8 blocked)</span>
            </div>
            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <span className="text-slate-600 font-medium">Hourly Rate Limit</span>
              <span className="font-semibold text-slate-900">Max 30 actions / hr</span>
            </div>
            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-xl">
              <span className="text-slate-600 font-medium">Token Storage</span>
              <span className="font-semibold text-emerald-600">AES-128 Fernet Encrypted</span>
            </div>
          </div>
          <button
            onClick={() => onNavigate('rules')}
            className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl transition-colors"
          >
            Configure Rules & Limits
          </button>
        </div>

        {/* Recent Activity Log Stream */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-5 border border-slate-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-slate-900 text-base">Recent Automated Actions</h3>
            <button
              onClick={() => onNavigate('logs')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800"
            >
              View Full Audit Log
            </button>
          </div>

          <div className="overflow-hidden">
            <div className="space-y-2.5">
              {(metrics?.recent_activity || []).length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center">No recent actions recorded yet.</p>
              ) : (
                metrics.recent_activity.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100 hover:bg-slate-100/70 transition-colors text-xs"
                  >
                    <div className="flex items-center space-x-3">
                      <span className={`w-2 h-2 rounded-full ${
                        item.status === 'success' ? 'bg-emerald-500' : item.status === 'failed' ? 'bg-rose-500' : 'bg-amber-500'
                      }`} />
                      <div>
                        <span className="font-semibold text-slate-800 uppercase tracking-wider text-[10px] mr-2 px-1.5 py-0.5 rounded bg-white border border-slate-200">
                          {item.action_type.replace('_', ' ')}
                        </span>
                        <span className="text-slate-600 font-medium">
                          {item.details?.sender ? `User: ${item.details.sender}` : item.details?.message || item.action_type}
                        </span>
                      </div>
                    </div>
                    <span className="text-slate-400 text-[11px]">
                      {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
