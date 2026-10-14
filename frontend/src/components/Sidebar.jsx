import React from 'react';
import { 
  LayoutDashboard, 
  Inbox, 
  Globe2, 
  Newspaper, 
  Sliders, 
  FileText, 
  FlaskConical 
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, pendingCount = 0 }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { 
      id: 'queue', 
      label: 'Approval Queue', 
      icon: Inbox, 
      badge: pendingCount > 0 ? pendingCount : null,
      badgeColor: 'bg-amber-500'
    },
    { id: 'pages', label: 'Connected Pages', icon: Globe2 },
    { id: 'posts', label: 'Posts & Feed', icon: Newspaper },
    { id: 'rules', label: 'Rules & Keywords', icon: Sliders },
    { id: 'logs', label: 'Audit Logs', icon: FileText },
    { id: 'simulator', label: 'Live Simulator', icon: FlaskConical },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200 min-h-[calc(100vh-65px)] p-4 flex flex-col justify-between shrink-0">
      <div className="space-y-1">
        <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 font-semibold shadow-xs'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="pt-4 border-t border-slate-100">
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1">
          <div className="font-semibold text-slate-700">Client Scope Status</div>
          <div className="text-slate-500">ANNEX A & MoE Compliant</div>
          <div className="text-[11px] text-blue-600 font-medium pt-1 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span> Policy Safe Rate-Limiter
          </div>
        </div>
      </div>
    </aside>
  );
}
