import React, { useState, useEffect } from 'react';
import {
  Globe2,
  Plus,
  RefreshCw,
  Settings2,
  Trash2,
  Eye,
  EyeOff,
  Check,
} from 'lucide-react';
import api from '../api';

export default function ConnectedPages({ onPagesUpdated }) {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPageToken, setShowPageToken] = useState(false);
  const [showUserToken, setShowUserToken] = useState(false);
  const [showEditPageToken, setShowEditPageToken] = useState(false);
  const [showEditUserToken, setShowEditUserToken] = useState(false);
  const [editingPage, setEditingPage] = useState(null);
  const [validatingId, setValidatingId] = useState(null);
  const [savingPage, setSavingPage] = useState(false);
  const [diagnosingToken, setDiagnosingToken] = useState(false);
  const [tokenDiagnostics, setTokenDiagnostics] = useState(null);
  const [connectError, setConnectError] = useState(null);
  const [connectNotice, setConnectNotice] = useState('');

  // New Page Form
  const [newPage, setNewPage] = useState({
    meta_page_id: '1285541747969599',
    name: 'PyLoom Technologies',
    category: 'E-Commerce & Digital Marketing',
    timezone: '',
    access_token: '',
    user_access_token: '',
    default_language: 'bilingual',
    response_tone: 'friendly',
    auto_approve_enabled: false,
    operating_hours_start: '08:00',
    operating_hours_end: '22:00',
    max_actions_per_hour: 30,
    brand_context: 'Client Facebook business page. Be polite, prompt, and helpful.',
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
    setSavingPage(true);
    setConnectError(null);
    setTokenDiagnostics(null);
    try {
      const pagePayload = { ...newPage };
      if (!pagePayload.timezone) delete pagePayload.timezone;
      const response = await api.post('/pages/', pagePayload);
      if (response.data.token_status !== 'valid') {
        throw new Error('Meta did not verify this Page connection.');
      }
      setConnectNotice(`${response.data.name} connected and validated with Meta.`);
      setShowAddModal(false);
      setShowPageToken(false);
      setShowUserToken(false);
      setNewPage({
        meta_page_id: '1285541747969599',
        name: 'PyLoom Technologies',
        category: 'E-Commerce & Digital Marketing',
        timezone: '',
        access_token: '',
        user_access_token: '',
        default_language: 'bilingual',
        response_tone: 'friendly',
        auto_approve_enabled: false,
        operating_hours_start: '08:00',
        operating_hours_end: '22:00',
        max_actions_per_hour: 30,
        brand_context: 'Client Facebook business page. Be polite, prompt, and helpful.',
      });
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      const metaError = err.metaError || {};
      setConnectError({
        message: [err.message, metaError.message]
          .filter((message, index, messages) => message && messages.indexOf(message) === index)
          .join(' — ') || 'Meta Page validation failed.',
        status: err.validationStatus,
        code: metaError.code,
        subcode: metaError.error_subcode,
      });
    } finally {
      setSavingPage(false);
      setNewPage((page) => ({ ...page, access_token: '', user_access_token: '' }));
      setShowPageToken(false);
      setShowUserToken(false);
    }
  };

  const handleDiagnoseToken = async () => {
    setDiagnosingToken(true);
    setConnectError(null);
    setTokenDiagnostics(null);
    try {
      const response = await api.post('/pages/diagnose-token', {
        meta_page_id: newPage.meta_page_id,
        access_token: newPage.access_token,
        user_access_token: newPage.user_access_token,
        name: newPage.name,
      });
      setTokenDiagnostics(response.data.checks);
    } catch (err) {
      const metaError = err.metaError || {};
      setConnectError({
        message: [err.message, metaError.message]
          .filter((message, index, messages) => message && messages.indexOf(message) === index)
          .join(' — ') || 'Read-only Meta diagnostics failed.',
        code: metaError.code,
        subcode: metaError.error_subcode,
      });
    } finally {
      setDiagnosingToken(false);
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

  const handleDiscoverInstagram = async (pageId) => {
    try {
      const response = await api.post(`/pages/${pageId}/instagram/discover`);
      setConnectNotice(
        response.data.instagram_username
          ? `Instagram @${response.data.instagram_username} connected.`
          : `Instagram account ${response.data.instagram_business_account_id} connected.`,
      );
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      alert(`Instagram account discovery failed: ${err.message}`);
    }
  };

  const handleValidateCredentials = async (pageId) => {
    setValidatingId(pageId);
    try {
      const response = await api.post(`/pages/${pageId}/validate-credentials`);
      const permissions = response.data.permissions?.join(', ') || 'none reported';
      const tasks = response.data.tasks?.join(', ') || 'none reported';
      alert(
        `Credential status: ${response.data.status}\n` +
        `Page token permissions: ${permissions}\n` +
        `Page access tasks: ${tasks}`
      );
      await fetchPages();
    } catch (err) {
      const metaError = err.metaError || {};
      const code = metaError.code ? `\nMeta error ${metaError.code}` : '';
      const subcode = metaError.error_subcode ? `/${metaError.error_subcode}` : '';
      alert(`Credential validation failed: ${err.message}${code}${subcode}`);
      await fetchPages();
    } finally {
      setValidatingId(null);
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
    setSavingPage(true);
    try {
      const { access_token, user_access_token, ...pageSettings } = editingPage;
      const payload = { ...pageSettings };
      if (access_token) {
        payload.access_token = access_token;
        if (user_access_token) payload.user_access_token = user_access_token;
      }
      await api.put(`/pages/${editingPage.id}`, payload);
      setEditingPage(null);
      setShowEditPageToken(false);
      setShowEditUserToken(false);
      await fetchPages();
      if (onPagesUpdated) onPagesUpdated();
    } catch (err) {
      const metaError = err.metaError || {};
      const code = metaError.code ? ` (Meta error ${metaError.code}` : '';
      const subcode = metaError.error_subcode ? `/${metaError.error_subcode}` : '';
      alert(`Update failed: ${err.message}${code ? `${code}${subcode})` : ''}`);
    } finally {
      setSavingPage(false);
      if (editingPage) {
        setEditingPage((page) => page ? { ...page, access_token: '', user_access_token: '' } : page);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">Connected Pages</h1>
          <p className="mt-0.5 text-sm text-[#5b6475]">
            Facebook Pages PyLoom can read and reply on.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="min-h-[44px] bg-[#1b2140] hover:bg-[#28315c] text-white rounded-[10px] px-4.5 text-sm font-semibold transition-colors flex items-center gap-2 cursor-pointer shadow-xs"
        >
          <Plus className="w-4 h-4" />
          <span>Connect a page</span>
        </button>
      </header>

      {connectNotice && (
        <div className="rounded-xl border border-[#0b6b4a]/20 bg-[#dff5ea] px-4 py-3 text-sm text-[#0b6b4a]" role="status">
          {connectNotice}
          <button className="ml-3 font-semibold underline cursor-pointer" onClick={() => setConnectNotice('')}>Dismiss</button>
        </div>
      )}

      {/* Pages Grid */}
      {loading && pages.length === 0 ? (
        <div className="p-16 text-center text-[#5b6475] bg-white rounded-2xl border border-[#e4e7ef]">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-[#1b2140]" />
          <p className="text-sm">Loading connected pages...</p>
        </div>
      ) : pages.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-2xl border border-[#e4e7ef] space-y-3">
          <Globe2 className="w-10 h-10 text-[#5b6475] mx-auto" />
          <h3 className="font-bold text-[#141a2e]">No Facebook Pages connected</h3>
          <p className="text-xs text-[#5b6475]">Connect a client Facebook Page to start automating.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {pages.map((page) => (
            <div
              key={page.id}
              className="bg-white rounded-2xl border border-[#e4e7ef] p-6 space-y-4 transition-shadow hover:shadow-xs"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-base font-bold text-[#141a2e]">{page.name}</h2>
                  <span className="text-[11px] text-[#5b6475] font-mono">ID: {page.meta_page_id}</span>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  page.token_status === 'valid'
                    ? 'bg-[#dff5ea] text-[#0b6b4a]'
                    : 'bg-[#ffe9c7] text-[#7a3f00]'
                }`}>
                  {page.token_status === 'valid' ? 'Connected' : page.token_status}
                </span>
              </div>

              {/* Rows */}
              <div className="divide-y divide-[#eceef5] text-sm">
                <div className="flex items-center justify-between py-2.5">
                  <span className="text-[#5b6475]">Automation</span>
                  <button
                    onClick={() => handleToggleAutomation(page.id)}
                    className={`w-11 h-6 rounded-full relative transition-colors cursor-pointer ${
                      page.automation_enabled ? 'bg-[#0b6b4a]' : 'bg-[#7d869a]'
                    }`}
                    role="switch"
                    aria-checked={page.automation_enabled}
                  >
                    <span
                      className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                        page.automation_enabled ? 'right-0.5' : 'left-0.5'
                      }`}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between py-2.5">
                  <span className="text-[#5b6475]">Reply mode</span>
                  <button
                    onClick={() => handleToggleAutoApprove(page)}
                    className="font-semibold text-xs text-[#141a2e] hover:text-[#2f3fb8] cursor-pointer"
                  >
                    {page.auto_approve_enabled ? 'Auto-pilot (Active)' : 'Supervised (Queue)'}
                  </button>
                </div>

                <div className="flex items-center justify-between py-2.5">
                  <span className="text-[#5b6475]">Last sync</span>
                  <b className="font-semibold text-[#141a2e]">
                    {page.last_synced_at ? new Date(page.last_synced_at).toLocaleTimeString() : 'Never'}
                  </b>
                </div>

                <div className="flex items-center justify-between py-2.5">
                  <span className="text-[#5b6475]">Instagram</span>
                  <span className="font-semibold text-[#141a2e]">
                    {page.instagram_business_account_id
                      ? `@${page.instagram_username || page.instagram_business_account_id}`
                      : 'Not connected'}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#eceef5]">
                <button
                  onClick={() => {
                    setEditingPage({ ...page, access_token: '', user_access_token: '' });
                    setShowEditPageToken(false);
                    setShowEditUserToken(false);
                  }}
                  className="min-h-[38px] px-3.5 rounded-[10px] border border-[#d5d9e6] hover:bg-[#f4f5f9] text-[#141a2e] text-xs font-semibold transition-colors cursor-pointer"
                >
                  Settings
                </button>
                <button
                  onClick={() => handleSyncPosts(page.id)}
                  className="min-h-[38px] px-3.5 rounded-[10px] border border-[#d5d9e6] hover:bg-[#f4f5f9] text-[#141a2e] text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3 text-[#5b6475]" />
                  <span>Sync feed</span>
                </button>
                <button
                  onClick={() => handleValidateCredentials(page.id)}
                  disabled={validatingId === page.id}
                  className="min-h-[38px] px-3.5 rounded-[10px] border border-[#d5d9e6] hover:bg-[#f4f5f9] text-[#141a2e] text-xs font-semibold disabled:opacity-50 cursor-pointer"
                >
                  {validatingId === page.id ? 'Validating…' : 'Validate'}
                </button>
                <button
                  onClick={() => handleDisconnect(page.id)}
                  className="min-h-[38px] px-3.5 rounded-[10px] border border-[#e9b8b8] hover:bg-[#fde4e4] text-[#a31f1f] text-xs font-semibold ml-auto transition-colors cursor-pointer"
                >
                  Disconnect
                </button>
              </div>
            </div>
          ))}

          {/* Add Another Page Dashed Card */}
          <div
            onClick={() => setShowAddModal(true)}
            className="border-2 border-dashed border-[#d5d9e6] hover:border-[#1b2140] bg-white rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-2 transition-colors cursor-pointer min-h-[220px]"
          >
            <div className="w-10 h-10 rounded-full bg-[#f4f5f9] flex items-center justify-center text-[#1b2140]">
              <Plus className="w-5 h-5" />
            </div>
            <div className="font-bold text-[#141a2e] text-base">Add another page</div>
            <p className="text-xs text-[#5b6475]">Sign in with Facebook and choose a page.</p>
            <button
              type="button"
              className="mt-2 min-h-[38px] bg-[#1b2140] text-white rounded-[10px] px-4 text-xs font-semibold cursor-pointer"
            >
              Connect a page
            </button>
          </div>
        </div>
      )}

      {/* Connect Page Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-[#e4e7ef] max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-[#141a2e]">Connect Facebook Page</h3>
            <p className="text-xs text-[#5b6475]">
              The Page token is stored encrypted after validation. A temporary User token is used only to verify Page tasks and is never saved.
            </p>
            <form onSubmit={handleCreatePage} className="space-y-3.5 text-xs">
              {connectError && (
                <div className="rounded-xl border border-[#e9b8b8] bg-[#fde4e4] p-3 text-xs text-[#a31f1f]" role="alert">
                  <p className="font-semibold">{connectError.message}</p>
                </div>
              )}
              {tokenDiagnostics && (
                <div className="rounded-xl border border-[#e4e7ef] bg-[#f4f5f9] p-3 text-xs text-[#141a2e]" role="status">
                  <p className="font-semibold mb-1">Read-only authentication diagnostics</p>
                  <p className="text-[#5b6475]">Checks finished. No Page record was created or modified.</p>
                </div>
              )}
              <div>
                <label className="block font-semibold text-[#5b6475] mb-1">Page Name *</label>
                <input
                  type="text"
                  required
                  value={newPage.name}
                  onChange={(e) => setNewPage({ ...newPage, name: e.target.value })}
                  placeholder="e.g. PyLoom Technologies"
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
                />
              </div>

              <div>
                <label className="block font-semibold text-[#5b6475] mb-1">Meta Page ID *</label>
                <input
                  type="text"
                  required
                  value={newPage.meta_page_id}
                  onChange={(e) => setNewPage({ ...newPage, meta_page_id: e.target.value })}
                  pattern="[0-9]+"
                  placeholder="e.g. 1285541747969599"
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm font-mono text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
                />
              </div>

              <div>
                <label htmlFor="page-access-token" className="block font-semibold text-[#5b6475] mb-1">
                  Page Access Token *
                </label>
                <div className="flex">
                  <input
                    id="page-access-token"
                    type={showPageToken ? 'text' : 'password'}
                    autoComplete="new-password"
                    spellCheck={false}
                    required
                    value={newPage.access_token}
                    onChange={(e) => {
                      setNewPage({ ...newPage, access_token: e.target.value });
                      setTokenDiagnostics(null);
                    }}
                    placeholder="Paste the Page access token"
                    className="w-full min-w-0 p-2.5 rounded-l-[10px] border border-r-0 border-[#d5d9e6] bg-white text-sm font-mono text-[#141a2e]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPageToken((visible) => !visible)}
                    className="flex items-center gap-1.5 rounded-r-[10px] border border-[#d5d9e6] bg-[#f4f5f9] px-3 text-[#5b6475] hover:bg-[#eceef5]"
                  >
                    {showPageToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label htmlFor="user-access-token" className="block font-semibold text-[#5b6475] mb-1">
                  Temporary User Access Token *
                </label>
                <div className="flex">
                  <input
                    id="user-access-token"
                    type={showUserToken ? 'text' : 'password'}
                    autoComplete="new-password"
                    spellCheck={false}
                    required
                    value={newPage.user_access_token}
                    onChange={(e) => {
                      setNewPage({ ...newPage, user_access_token: e.target.value });
                      setTokenDiagnostics(null);
                    }}
                    placeholder="Used only for read-only validation check"
                    className="w-full min-w-0 p-2.5 rounded-l-[10px] border border-r-0 border-[#d5d9e6] bg-white text-sm font-mono text-[#141a2e]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowUserToken((visible) => !visible)}
                    className="flex items-center gap-1.5 rounded-r-[10px] border border-[#d5d9e6] bg-[#f4f5f9] px-3 text-[#5b6475] hover:bg-[#eceef5]"
                  >
                    {showUserToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false);
                    setShowPageToken(false);
                    setShowUserToken(false);
                    setConnectError(null);
                    setNewPage((page) => ({ ...page, access_token: '', user_access_token: '' }));
                  }}
                  disabled={savingPage}
                  className="px-4 py-2 rounded-[10px] border border-[#d5d9e6] text-[#5b6475] hover:text-[#141a2e] font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDiagnoseToken}
                  disabled={savingPage || diagnosingToken || !newPage.access_token || !newPage.user_access_token}
                  className="px-4 py-2 rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] text-[#141a2e] font-semibold disabled:opacity-50 cursor-pointer"
                >
                  {diagnosingToken ? 'Checking…' : 'Run Check'}
                </button>
                <button
                  type="submit"
                  disabled={savingPage || diagnosingToken}
                  className="px-5 py-2 rounded-[10px] bg-[#1b2140] hover:bg-[#28315c] text-white font-bold disabled:opacity-50 cursor-pointer"
                >
                  {savingPage ? 'Validating…' : 'Save & Connect'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Page Settings Modal */}
      {editingPage && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-[#e4e7ef] max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-[#141a2e]">Configure Page: {editingPage.name}</h3>
            <form onSubmit={handleUpdatePageSettings} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-[#5b6475] mb-1">Timezone</label>
                <input
                  type="text"
                  required
                  value={editingPage.timezone || 'Asia/Kathmandu'}
                  onChange={(e) => setEditingPage({ ...editingPage, timezone: e.target.value })}
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-[#5b6475] mb-1">Operating Hours Start</label>
                  <input
                    type="time"
                    value={editingPage.operating_hours_start}
                    onChange={(e) => setEditingPage({ ...editingPage, operating_hours_start: e.target.value })}
                    className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2 text-sm text-[#141a2e]"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[#5b6475] mb-1">Operating Hours End</label>
                  <input
                    type="time"
                    value={editingPage.operating_hours_end}
                    onChange={(e) => setEditingPage({ ...editingPage, operating_hours_end: e.target.value })}
                    className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2 text-sm text-[#141a2e]"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-[#5b6475] mb-1">Max Actions / Hour</label>
                <input
                  type="number"
                  min="5"
                  max="100"
                  value={editingPage.max_actions_per_hour}
                  onChange={(e) => setEditingPage({ ...editingPage, max_actions_per_hour: parseInt(e.target.value) })}
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2 text-sm text-[#141a2e]"
                />
              </div>

              <div>
                <label className="block font-semibold text-[#5b6475] mb-1">Brand Context for AI</label>
                <textarea
                  rows={3}
                  value={editingPage.brand_context}
                  onChange={(e) => setEditingPage({ ...editingPage, brand_context: e.target.value })}
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-xs text-[#141a2e]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingPage(null)}
                  className="px-4 py-2 rounded-[10px] border border-[#d5d9e6] text-[#5b6475] hover:text-[#141a2e] font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-[10px] bg-[#1b2140] hover:bg-[#28315c] text-white font-bold cursor-pointer"
                >
                  Save settings
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
