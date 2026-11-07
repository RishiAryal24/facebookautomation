import React from 'react';
import { ArrowRight, Play, CheckCircle2 } from 'lucide-react';

export default function Dashboard({ metrics, onNavigate, onSimulateQuick }) {
  const pendingCount = metrics?.pending_approvals_count || 0;

  const statCards = [
    {
      title: 'Connected pages',
      value: metrics?.total_pages_connected || 0,
      actionText: 'Manage pages →',
      tab: 'pages',
    },
    {
      title: 'Monitored posts',
      value: metrics?.total_posts_monitored || 0,
      actionText: 'View feed →',
      tab: 'posts',
    },
    {
      title: 'Comments ingested',
      value: metrics?.total_comments_received || 0,
      actionText: 'View posts →',
      tab: 'posts',
    },
    {
      title: 'Published AI replies',
      value: metrics?.published_replies_count || 0,
      actionText: 'Audit logs →',
      tab: 'logs',
    },
    {
      title: 'Likes & reactions',
      value: metrics?.total_likes_given || 0,
      actionText: 'Engagement settings →',
      tab: 'rules',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Greeting Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">Good morning</h1>
          <p className="text-sm text-[#5b6475] mt-0.5">
            Bilingual AI engagement for Facebook Pages · English &amp; <span className="font-devanagari">नेपाली</span>
          </p>
        </div>
      </header>

      {/* Hero Attention Card */}
      <section className="bg-[#1b2140] text-white rounded-[20px] p-7 md:p-8 flex flex-wrap gap-6 items-center justify-between shadow-sm">
        <div className="max-w-xl">
          <div className="text-[13px] font-semibold text-[#aab4ff] mb-2">Needs your attention</div>
          <div className="text-2xl md:text-[28px] font-bold tracking-tight leading-snug">
            {pendingCount > 0
              ? `${pendingCount} AI ${pendingCount === 1 ? 'reply is' : 'replies are'} waiting for approval`
              : 'All caught up · 0 replies waiting for approval'}
          </div>
          <p className="text-sm text-[#c8cde6] mt-2 leading-relaxed">
            Review each draft before it goes live. Approved replies are posted within the 30 actions per hour limit.
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={() => onNavigate('queue')}
            className="min-h-[46px] bg-[#ffb84d] hover:bg-[#ffc670] text-[#2a1700] border-0 rounded-xl px-5.5 text-sm font-bold transition-colors cursor-pointer shadow-xs"
          >
            Review queue ({pendingCount})
          </button>
          <button
            onClick={() => onNavigate('simulator')}
            className="min-h-[46px] bg-transparent hover:bg-white/10 text-white border border-[#5a6390] rounded-xl px-5.5 text-sm font-semibold transition-colors cursor-pointer flex items-center gap-2"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Test live comment</span>
          </button>
        </div>
      </section>

      {/* Metric Stat Cards Grid */}
      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map((card, idx) => (
          <div
            key={idx}
            className="bg-white border border-[#e4e7ef] rounded-2xl p-5 flex flex-col justify-between transition-shadow hover:shadow-xs"
          >
            <div className="text-[13px] text-[#5b6475] font-medium">{card.title}</div>
            <div className="text-[34px] font-bold text-[#141a2e] my-1.5 tracking-tight leading-none">
              {card.value}
            </div>
            <button
              onClick={() => onNavigate(card.tab)}
              className="text-[13px] font-semibold text-[#2f3fb8] hover:underline text-left inline-flex items-center gap-1 cursor-pointer pt-1"
            >
              <span>{card.actionText}</span>
            </button>
          </div>
        ))}
      </section>

      {/* 2-Column Split: Recent Actions & Policy Guardrails */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        {/* Recent Automated Actions */}
        <div className="bg-white border border-[#e4e7ef] rounded-2xl p-5.5 flex flex-col">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-base font-bold text-[#141a2e]">Recent automated actions</h2>
            <button
              onClick={() => onNavigate('logs')}
              className="text-[13px] font-semibold text-[#2f3fb8] hover:underline cursor-pointer"
            >
              Full audit log →
            </button>
          </div>

          <div className="divide-y divide-[#eceef5]">
            {(metrics?.recent_activity || []).length === 0 ? (
              <p className="text-sm text-[#5b6475] py-8 text-center">No recent actions recorded yet.</p>
            ) : (
              metrics.recent_activity.slice(0, 6).map((item) => (
                <div key={item.id} className="flex items-center gap-3 py-3 text-sm">
                  <span
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      item.status === 'success'
                        ? 'bg-[#12875f]'
                        : item.status === 'failed'
                        ? 'bg-[#a31f1f]'
                        : 'bg-[#c97700]'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-[#141a2e] capitalize">
                      {item.action_type.replaceAll('_', ' ')}
                    </div>
                    <div className="text-xs text-[#5b6475] truncate">
                      {item.details?.sender
                        ? `User: ${item.details.sender}`
                        : item.details?.message || item.action_type}
                    </div>
                  </div>
                  <span className="text-xs text-[#5b6475] shrink-0 font-mono">
                    {new Date(item.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Safety & Policy Guardrails */}
        <div className="bg-white border border-[#e4e7ef] rounded-2xl p-5.5 flex flex-col">
          <h2 className="text-base font-bold text-[#141a2e] mb-2">Safety &amp; policy guardrails</h2>
          <div className="divide-y divide-[#eceef5] text-sm">
            <div className="flex justify-between items-center py-3">
              <span className="text-[#5b6475]">Bilingual support</span>
              <span className="font-semibold text-[#141a2e]">
                English + <span className="font-devanagari">नेपाली</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-[#5b6475]">Restricted keyword filter</span>
              <span className="font-semibold text-[#0b6b4a]">Active · 8 blocked</span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-[#5b6475]">Hourly rate limit</span>
              <span className="font-semibold text-[#141a2e]">30 actions / hr</span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-[#5b6475]">Token encryption</span>
              <span className="font-semibold text-[#0b6b4a]">AES-128 Fernet</span>
            </div>
          </div>
          <button
            onClick={() => onNavigate('rules')}
            className="mt-4 w-full min-h-[42px] bg-[#f4f5f9] hover:bg-[#eceef5] text-[#141a2e] border border-[#e4e7ef] rounded-xl text-xs font-semibold transition-colors cursor-pointer"
          >
            Configure Rules &amp; Limits
          </button>
        </div>
      </section>
    </div>
  );
}
