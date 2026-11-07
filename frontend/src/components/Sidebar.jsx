import React from 'react';
import {
  LayoutDashboard,
  CheckSquare,
  Globe2,
  Newspaper,
  Sparkles,
  Megaphone,
  Sliders,
  FileText,
  FlaskConical,
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, pendingCount = 0 }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    {
      id: 'queue',
      label: 'Approval Queue',
      icon: CheckSquare,
      badge: pendingCount > 0 ? pendingCount : null,
    },
    { id: 'pages', label: 'Connected Pages', icon: Globe2 },
    { id: 'posts', label: 'Posts & Feed', icon: Newspaper },
    { id: 'content', label: 'AI Content', icon: Sparkles },
    { id: 'ads', label: 'Advertising', icon: Megaphone },
    { id: 'rules', label: 'Rules & Keywords', icon: Sliders },
    { id: 'logs', label: 'Audit Logs', icon: FileText },
    { id: 'simulator', label: 'Live Simulator', icon: FlaskConical },
  ];

  return (
    <aside className="w-[236px] bg-white border-r border-[#e4e7ef] min-h-[calc(100vh-65px)] p-4 flex flex-col gap-1 shrink-0 select-none">
      {/* Brand Header */}
      <div className="flex items-center gap-2.5 px-1.5 pb-4.5 mb-1">
        <div className="w-9 h-9 rounded-[10px] bg-[#1b2140] text-white grid place-items-center font-bold text-sm shrink-0 shadow-xs">
          PL
        </div>
        <div>
          <div className="font-bold text-[15px] text-[#141a2e] leading-tight">PyLoom</div>
          <div className="text-[12px] text-[#5b6475] leading-tight">Automation · v1.0 MoE</div>
        </div>
      </div>

      {/* Nav List */}
      <nav className="flex-1 flex flex-col gap-1" aria-label="Main Navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 min-h-[44px] rounded-[10px] text-sm font-medium transition-colors text-left ${
                isActive
                  ? 'bg-[#1b2140] text-white font-semibold'
                  : 'text-[#4a5365] hover:bg-[#eef0f6] hover:text-[#141a2e]'
              }`}
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-[#5b6475]'}`} />
              <span className="flex-1 truncate">{item.label}</span>
              {item.badge !== null && item.badge !== undefined && (
                <span
                  className={`text-[12px] font-bold px-2 py-0.5 rounded-full ${
                    isActive
                      ? 'bg-[#ffb84d] text-[#2a1700]'
                      : 'bg-[#ffe3b8] text-[#7a3f00]'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Client Scope Status Box */}
      <div className="mt-4 pt-3 border-t border-[#eceef5]">
        <div className="bg-[#f4f5f9] rounded-xl p-3.5 text-xs text-[#5b6475] leading-relaxed">
          <div className="font-semibold text-[#141a2e] text-[13px] mb-0.5">Client scope</div>
          <div>ANNEX A &amp; MoE compliant</div>
          <div className="text-[#0b6b4a] font-semibold mt-1.5 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#12875f] animate-pulse"></span>
            Rate limiter on
          </div>
        </div>
      </div>
    </aside>
  );
}
