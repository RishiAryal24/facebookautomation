import React, { useState, useEffect } from 'react';
import { 
  Globe2, 
  Plus, 
  RefreshCw, 
  Settings2, 
  Trash2, 
  CheckCircle2, 
  AlertCircle,
  ToggleLeft,
  ToggleRight,
  Shield,
  Clock,
  Sparkles
} from 'lucide-react';
import api from '../api';

export default function ConnectedPages({ onPagesUpdated }) {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingPage, setEditingPage] = useState(null);

  // New Page Form
  const [newPage, setNewPage] = useState({
    meta_page_id: '',
    name: '',
    category: 'E-Commerce & Digital Marketing',
    access_token: '',
    default_language: 'bilingual',
    response_tone: 'friendly',
    auto_approve_enabled: false,
    operating_hours_start: '08:00',
    operating_hours_end: '22:00',
    max_actions_per_hour: 30,
    brand_context: 'Client Facebook business page. Be polite, prompt, and helpful.'
  });

  const fetchPages = async () => {
    setLoading(true);
    try {
      const res = await api.get('/pages/');
      setPages(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPages();
  }, []);

  const handleCreatePage = async (e) => {
    e.preventDefault();
    try {
      await api.post('/pages/', newPage);
      setShowAddModal(false);
      setNewPage({
        meta_page_id: '',
        name: '',
        category: 'E-Commerce & Digital Marketing',
        access_token: '',
        default_language: 'bilingual',
        response_tone: 'friendly',
        auto_approve_enabled: false,
        operating_hours_start: '08:00',
        operating_hours_end: '22:00',
        max_actions_per_hour: 30,
        brand_context: 'Client Facebook business page. Be polite, prompt, and helpful.'
      });
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      alert('Failed to connect page: ' + err.message);
    }
  };

  const handleToggleAutomation = async (pageId) => {
    try {
      await api.post(`/pages/${pageId}/toggle-automation`);
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      alert('Failed to toggle automation: ' + err.message);
    }
  };

  const handleToggleAutoApprove = async (page) => {
    try {
      await api.put(`/pages/${page.id}`, {
        auto_approve_enabled: !page.auto_approve_enabled,
      });
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      alert('Failed to update approval mode: ' + err.message);
    }
  };

  const handleSyncPosts = async (pageId) => {
    try {
      const res = await api.post(`/pages/${pageId}/sync`);
      alert(`Sync successful! ${res.data.synced_posts} posts retrieved (${res.data.new_posts_added} new added).`);
      await fetchPages();
    } catch (err) {
      alert('Sync failed: ' + err.message);
    }
  };

  const handleDisconnect = async (pageId) => {
    if (!confirm('Are you sure you want to disconnect this Facebook Page? All local scheduled actions will stop.')) return;
    try {
      await api.delete(`/pages/${pageId}`);
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      alert('Disconnect failed: ' + err.message);
    }
  };

  const handleUpdatePageSettings = async (e) => {
    e.preventDefault();
    if (!editingPage) return;
    try {
      await api.put(`/pages/${editingPage.id}`, editingPage);
      setEditingPage(null);
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      alert('Update failed: ' + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Connected Facebook Pages</h2>
          <p className="text-xs text-slate-500 mt-1">
            Meta OAuth authorized Pages, operating schedules, and rate limiting (ANNEX A §2.2).
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          <span>Connect Facebook Page</span>
        </button>
      </div>

      {/* Pages List */}
      {loading && pages.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
          <p className="text-sm">Loading connected pages...</p>
        </div>
      ) : pages.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-3">
          <Globe2 className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="font-bold text-slate-800">No Facebook Pages Connected</h3>
          <p className="text-xs text-slate-500">Connect a client Facebook Page to start automating.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {pages.map((page) => (
            <div
              key={page.id}
              className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 rounded-xl bg-blue-100 overflow-hidden shrink-0 border border-slate-200">
                    {page.picture_url ? (
                      <img src={page.picture_url} alt={page.name} className="w-full h-full object-cover" />
                    ) : (
                      <Globe2 className="w-6 h-6 text-blue-600 m-3" />
                    )}
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{page.name}</h3>
                    <p className="text-xs text-slate-500">{page.category || 'Business Page'}</p>
                    <span className="text-[10px] text-slate-400 font-mono">ID: {page.meta_page_id}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-1">
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                    page.automation_enabled ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'
                  }`}>
                    {page.automation_enabled ? 'Active' : 'Paused'}
                  </span>
                </div>
              </div>

              {/* Toggles and Mode */}
              <div className="p-3 bg-slate-50 rounded-xl space-y-2.5 text-xs">
                {/* Automation Global Toggle */}
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-700">Automation State</span>
                  <button
                    onClick={() => handleToggleAutomation(page.id)}
                    className="font-semibold text-xs flex items-center gap-1 text-slate-800 hover:text-blue-600"
                  >
                    {page.automation_enabled ? (
                      <span className="text-emerald-600 flex items-center gap-1 font-bold">
                        <ToggleRight className="w-6 h-6 text-emerald-600" /> Enabled
                      </span>
                    ) : (
                      <span className="text-slate-400 flex items-center gap-1 font-bold">
                        <ToggleLeft className="w-6 h-6 text-slate-400" /> Paused
                      </span>
                    )}
                  </button>
                </div>

                {/* Auto-Approve Toggle */}
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-slate-700 block">Approval Mode</span>
                    <span className="text-[11px] text-slate-400">
                      {page.auto_approve_enabled ? '100% Full Auto-Publish' : 'Supervised (Approval Queue)'}
                    </span>
                  </div>
                  <button
                    onClick={() => handleToggleAutoApprove(page)}
                    className="font-semibold text-xs flex items-center gap-1"
                  >
                    {page.auto_approve_enabled ? (
                      <span className="text-purple-600 flex items-center gap-1 font-bold">
                        <ToggleRight className="w-6 h-6 text-purple-600" /> Auto-Pilot
                      </span>
                    ) : (
                      <span className="text-amber-600 flex items-center gap-1 font-bold">
                        <ToggleLeft className="w-6 h-6 text-amber-500" /> Queue First
                      </span>
                    )}
                  </button>
                </div>

                {/* Stats */}
                <div className="pt-2 border-t border-slate-200 flex justify-between text-slate-500 text-[11px]">
                  <span>Replies: <strong>{page.total_comments_replied}</strong></span>
                  <span>Likes: <strong>{page.total_likes_given}</strong></span>
                  <span>Rate: <strong>{page.max_actions_per_hour}/hr</strong></span>
                  <span>Hours: <strong>{page.operating_hours_start}-{page.operating_hours_end}</strong></span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1">
                <button
                  onClick={() => handleSyncPosts(page.id)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Sync Feed</span>
                </button>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setEditingPage(page)}
                    className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
                    title="Settings"
                  >
                    <Settings2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDisconnect(page.id)}
                    className="p-1.5 rounded-lg border border-slate-200 hover:bg-rose-50 hover:text-rose-600 transition-colors"
                    title="Disconnect"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Connect Page Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Connect Facebook Page</h3>
            <p className="text-xs text-slate-500">
              Enter your Meta Page ID and Page Access Token. In simulation mode, you can use any mock ID.
            </p>
            <form onSubmit={handleCreatePage} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Page Name *</label>
                <input
                  type="text"
                  required
                  value={newPage.name}
                  onChange={(e) => setNewPage({ ...newPage, name: e.target.value })}
                  placeholder="e.g. PyLoom Retail Store"
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Meta Page ID *</label>
                <input
                  type="text"
                  required
                  value={newPage.meta_page_id}
                  onChange={(e) => setNewPage({ ...newPage, meta_page_id: e.target.value })}
                  placeholder="e.g. 10928374829102"
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-sm font-mono focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Page Access Token (Encrypted with AES-128)</label>
                <input
                  type="password"
                  value={newPage.access_token}
                  onChange={(e) => setNewPage({ ...newPage, access_token: e.target.value })}
                  placeholder="EAA... (Leave blank or prefix mock_ for simulation mode)"
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-sm font-mono focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Response Language</label>
                  <select
                    value={newPage.default_language}
                    onChange={(e) => setNewPage({ ...newPage, default_language: e.target.value })}
                    className="w-full p-2.5 rounded-xl border border-slate-300 bg-white"
                  >
                    <option value="bilingual">Bilingual (English + Nepali)</option>
                    <option value="ne">Nepali Only (नेपाली)</option>
                    <option value="en">English Only</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Brand Voice / Tone</label>
                  <select
                    value={newPage.response_tone}
                    onChange={(e) => setNewPage({ ...newPage, response_tone: e.target.value })}
                    className="w-full p-2.5 rounded-xl border border-slate-300 bg-white"
                  >
                    <option value="friendly">Friendly & Attentive</option>
                    <option value="professional">Professional</option>
                    <option value="support">Helpful Support</option>
                    <option value="promotional">Sales & Conversions</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Brand Context & FAQs for AI</label>
                <textarea
                  rows={2}
                  value={newPage.brand_context}
                  onChange={(e) => setNewPage({ ...newPage, brand_context: e.target.value })}
                  className="w-full p-2 rounded-xl border border-slate-300 text-xs"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold"
                >
                  Save & Connect
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Page Settings Modal */}
      {editingPage && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Configure Page: {editingPage.name}</h3>
            <form onSubmit={handleUpdatePageSettings} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Operating Hours Start</label>
                  <input
                    type="time"
                    value={editingPage.operating_hours_start}
                    onChange={(e) => setEditingPage({ ...editingPage, operating_hours_start: e.target.value })}
                    className="w-full p-2 rounded-xl border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Operating Hours End</label>
                  <input
                    type="time"
                    value={editingPage.operating_hours_end}
                    onChange={(e) => setEditingPage({ ...editingPage, operating_hours_end: e.target.value })}
                    className="w-full p-2 rounded-xl border border-slate-300"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Max Actions / Hour (Rate Limit)</label>
                <input
                  type="number"
                  min="5"
                  max="100"
                  value={editingPage.max_actions_per_hour}
                  onChange={(e) => setEditingPage({ ...editingPage, max_actions_per_hour: parseInt(e.target.value) })}
                  className="w-full p-2 rounded-xl border border-slate-300"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Brand Knowledge & Instructions</label>
                <textarea
                  rows={3}
                  value={editingPage.brand_context}
                  onChange={(e) => setEditingPage({ ...editingPage, brand_context: e.target.value })}
                  className="w-full p-2.5 rounded-xl border border-slate-300"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingPage(null)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold"
                >
                  Save Settings
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
