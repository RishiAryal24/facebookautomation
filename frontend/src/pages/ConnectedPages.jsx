import React, { useState, useEffect } from 'react';
import { 
  Globe2, 
  Plus, 
  RefreshCw, 
  Settings2, 
  Trash2, 
  ToggleLeft,
  ToggleRight,
  Eye,
  EyeOff,
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
        brand_context: 'Client Facebook business page. Be polite, prompt, and helpful.'
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Connected Facebook Pages</h2>
          <p className="text-xs text-slate-500 mt-1">
            Connected Pages, credential status, operating schedules, and rate limiting (ANNEX A §2.2).
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

      {connectNotice && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">
          {connectNotice}
          <button className="ml-3 font-semibold underline" onClick={() => setConnectNotice('')}>Dismiss</button>
        </div>
      )}

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
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                    page.token_status === 'valid'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : page.token_status === 'expiring_soon'
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : page.token_status === 'reauthorization_required'
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : page.token_status === 'permission_missing'
                      ? 'bg-orange-50 text-orange-700 border border-orange-200'
                      : page.token_status === 'simulated'
                      ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                      : 'bg-rose-50 text-rose-700 border border-rose-200'
                  }`}>
                    {page.token_status === 'valid'
                      ? 'Connected'
                      : page.token_status === 'expiring_soon'
                      ? 'Expiring soon'
                      : page.token_status === 'reauthorization_required'
                      ? 'Reauthorization required'
                      : page.token_status === 'permission_missing'
                      ? 'Permission missing'
                      : page.token_status === 'simulated'
                      ? 'Simulation'
                      : page.token_status === 'connection_failed'
                      ? 'Connection failed'
                      : 'Validation pending'}
                  </span>
                </div>
                {page.last_validated_at && (
                  <p className="text-[10px] text-slate-400">
                    Last verified: {new Date(page.last_validated_at).toLocaleString()}
                    {page.meta_app_id ? ` · Meta App ${page.meta_app_id}` : ''}
                  </p>
                )}
              </div>

              <div className="text-[10px] text-slate-500">
                <span>
                  pages_manage_posts: {page.granted_permissions?.includes('pages_manage_posts') ? 'granted' : 'missing'}
                </span>
                <span className="mx-2">·</span>
                <span>
                  pages_read_engagement: {page.granted_permissions?.includes('pages_read_engagement') ? 'granted' : 'missing'}
                </span>
                <span className="mx-2">·</span>
                <span>
                  CREATE_CONTENT: {page.page_tasks?.includes('CREATE_CONTENT') ? 'granted' : 'missing'}
                </span>
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
                      {page.auto_approve_enabled ? 'Safety-checked auto-publish' : 'Supervised (Approval Queue)'}
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
                  <span>Zone: <strong>{page.timezone}</strong></span>
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
                    onClick={() => handleValidateCredentials(page.id)}
                    disabled={validatingId === page.id}
                    className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 text-xs font-semibold disabled:opacity-50"
                  >
                    {validatingId === page.id ? 'Validating…' : 'Validate'}
                  </button>
                  <button
                    onClick={() => {
                      setEditingPage({ ...page, access_token: '', user_access_token: '' });
                      setShowEditPageToken(false);
                      setShowEditUserToken(false);
                    }}
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
              The Page token is stored encrypted after validation. A temporary User token is used only to verify Page tasks and is never saved.
            </p>
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Read-only checks work while simulation is on. Publishing stays disabled until Page permissions and CREATE_CONTENT are verified and you switch to live mode.
            </p>
            <form onSubmit={handleCreatePage} className="space-y-3.5 text-xs">
              {connectError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert">
                  <p className="font-semibold">{connectError.message}</p>
                  {connectError.status && <p>Status: {connectError.status.replaceAll('_', ' ')}</p>}
                  {(connectError.code || connectError.subcode) && (
                    <p>Meta error: {connectError.code || 'unknown'}{connectError.subcode ? ` / ${connectError.subcode}` : ''}</p>
                  )}
                  <p className="mt-1">The Page was not connected and the token was not stored.</p>
                </div>
              )}
              {tokenDiagnostics && (
                <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950" role="status">
                  <p className="font-semibold">Read-only authentication comparison</p>
                  <p className="mb-2">The Page and temporary User tokens were sent unchanged. No Page record was created or modified.</p>
                  <div className="space-y-1">
                    {[
                      ['page_read_without_appsecret_proof', 'Page read without appsecret_proof'],
                      ['page_read_with_appsecret_proof', 'Page read with appsecret_proof'],
                      ['page_tasks_via_accounts_edge', 'Page task access via /me/accounts'],
                      ['user_token_debug_token', 'Temporary User token debug_token validation'],
                      ['app_identity', 'Configured App ID / Secret identity'],
                      ['debug_token', 'Page token debug_token validation'],
                    ].map(([key, label]) => {
                      const check = tokenDiagnostics[key];
                      const error = check?.meta_error || {};
                      const result = check?.result || {};
                      const pageDetails = result.id
                        ? ` — ${result.name || 'Page'} (${result.id})`
                        : result.name
                          ? ` — ${result.name} (${result.id || 'ID unavailable'})`
                          : '';
                      const pageTaskDetails = Array.isArray(result.items)
                        ? ` — ${result.items.map((item) => `${item.id}: ${(item.tasks || []).join(', ') || 'no tasks returned'}`).join('; ') || 'Page ID not returned'}`
                        : '';
                      const debugDetails = result.app_id
                        ? ` — app ${result.app_id}, ${result.type || 'type unknown'}, ${result.is_valid ? 'valid' : 'invalid'}${Array.isArray(result.scopes) ? `; scopes: ${result.scopes.join(', ')}` : ''}`
                        : '';
                      return (
                        <p key={key}>
                          <strong>{label}:</strong>{' '}
                          {check?.success ? `HTTP ${check.http_status}${pageDetails}${pageTaskDetails}${debugDetails}` : `HTTP ${check?.http_status ?? 'not sent'}${error.code ? `, error ${error.code}${error.error_subcode ? `/${error.error_subcode}` : ''}` : ''}${error.message ? ` — ${error.message}` : ''}`}
                        </p>
                      );
                    })}
                  </div>
                </div>
              )}
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
                  pattern="[0-9]+"
                  placeholder="e.g. 10928374829102"
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-sm font-mono focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="page-access-token" className="block font-semibold text-slate-700 mb-1">
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
                    className="w-full min-w-0 p-2.5 rounded-l-xl border border-r-0 border-slate-300 text-sm font-mono focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPageToken((visible) => !visible)}
                    aria-label={showPageToken ? 'Hide Page access token' : 'Show Page access token'}
                    aria-pressed={showPageToken}
                    className="flex items-center gap-1.5 rounded-r-xl border border-slate-300 bg-slate-50 px-3 text-slate-600 hover:bg-slate-100"
                  >
                    {showPageToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    <span>{showPageToken ? 'Hide' : 'Show'}</span>
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Stored encrypted by the backend. Never share this token in chat or screenshots.
                </p>
              </div>

              <div>
                <label htmlFor="user-access-token" className="block font-semibold text-slate-700 mb-1">
                  Temporary User Access Token (required for CREATE_CONTENT check) *
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
                    placeholder="Used only for the read-only Page task check"
                    className="w-full min-w-0 p-2.5 rounded-l-xl border border-r-0 border-slate-300 text-sm font-mono focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowUserToken((visible) => !visible)}
                    aria-label={showUserToken ? 'Hide temporary User access token' : 'Show temporary User access token'}
                    aria-pressed={showUserToken}
                    className="flex items-center gap-1.5 rounded-r-xl border border-slate-300 bg-slate-50 px-3 text-slate-600 hover:bg-slate-100"
                  >
                    {showUserToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    <span>{showUserToken ? 'Hide' : 'Show'}</span>
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Sent only for read-only validation through /me/accounts. Never stored or returned.
                </p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Page Timezone (IANA)</label>
                <input
                  type="text"
                  value={newPage.timezone}
                  onChange={(e) => setNewPage({ ...newPage, timezone: e.target.value })}
                  placeholder="Asia/Kathmandu"
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-sm"
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
                  onClick={() => {
                    setShowAddModal(false);
                    setShowPageToken(false);
                    setShowUserToken(false);
                    setConnectError(null);
                    setNewPage((page) => ({ ...page, access_token: '', user_access_token: '' }));
                  }}
                  disabled={savingPage}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDiagnoseToken}
                  disabled={savingPage || diagnosingToken || !newPage.access_token || !newPage.user_access_token}
                  className="px-4 py-2 rounded-xl border border-sky-300 text-sky-800 font-semibold disabled:opacity-50"
                >
                  {diagnosingToken ? 'Checking with Meta…' : 'Run Read-Only Check'}
                </button>
                <button
                  type="submit"
                  disabled={savingPage || diagnosingToken}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold disabled:opacity-50"
                >
                  {savingPage ? 'Validating with Meta…' : 'Save & Connect'}
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
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Replace Page access token (optional)</label>
                <div className="flex">
                  <input
                    type={showEditPageToken ? 'text' : 'password'}
                    autoComplete="new-password"
                    spellCheck={false}
                    value={editingPage.access_token || ''}
                    onChange={(e) => setEditingPage({ ...editingPage, access_token: e.target.value })}
                    placeholder="Leave blank to keep the current token"
                    className="w-full min-w-0 p-2 rounded-l-xl border border-r-0 border-slate-300 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowEditPageToken((visible) => !visible)}
                    className="px-3 rounded-r-xl border border-slate-300 text-slate-600"
                    aria-label={showEditPageToken ? 'Hide Page access token' : 'Show Page access token'}
                  >
                    {showEditPageToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  A replacement token is checked with Meta before it is encrypted and saved. Simulation stays on.
                </p>
              </div>
              {editingPage.access_token && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Temporary User Access Token (required for CREATE_CONTENT)</label>
                  <div className="flex">
                    <input
                      type={showEditUserToken ? 'text' : 'password'}
                      autoComplete="new-password"
                      spellCheck={false}
                      value={editingPage.user_access_token || ''}
                      onChange={(e) => setEditingPage({ ...editingPage, user_access_token: e.target.value })}
                      placeholder="Used only for the read-only Page task check"
                      className="w-full min-w-0 p-2 rounded-l-xl border border-r-0 border-slate-300 font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowEditUserToken((visible) => !visible)}
                      className="px-3 rounded-r-xl border border-slate-300 text-slate-600"
                      aria-label={showEditUserToken ? 'Hide temporary User access token' : 'Show temporary User access token'}
                    >
                      {showEditUserToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Used only for read-only CREATE_CONTENT validation; never stored or returned.
                  </p>
                </div>
              )}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Page Timezone (IANA)</label>
                <input
                  type="text"
                  required
                  value={editingPage.timezone || 'Asia/Kathmandu'}
                  onChange={(e) => setEditingPage({ ...editingPage, timezone: e.target.value })}
                  placeholder="Asia/Kathmandu"
                  className="w-full p-2 rounded-xl border border-slate-300"
                />
              </div>
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
