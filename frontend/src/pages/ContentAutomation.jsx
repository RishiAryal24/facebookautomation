import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CalendarClock,
  Check,
  Clock3,
  History,
  ImagePlus,
  LoaderCircle,
  Pencil,
  RefreshCw,
  RotateCw,
  Save,
  Send,
  Settings2,
  Sparkles,
  ThumbsDown,
  X,
} from 'lucide-react';
import api from '../api';

const TABS = [
  { id: 'generate', label: 'Generator' },
  { id: 'drafts', label: 'Approval Queue' },
  { id: 'scheduled', label: 'Scheduled Content' },
  { id: 'history', label: 'Generation History' },
];

const errorText = (error) => error?.message || 'The request failed. Please try again.';

export default function ContentAutomation({ simulationMode = true }) {
  const [pages, setPages] = useState([]);
  const [pageId, setPageId] = useState('');
  const [config, setConfig] = useState(null);
  const [configForm, setConfigForm] = useState(null);
  const [posts, setPosts] = useState([]);
  const [scheduled, setScheduled] = useState([]);
  const [history, setHistory] = useState({ generation_runs: [], content_versions: [] });
  const [tab, setTab] = useState('generate');
  const [topic, setTopic] = useState('');
  const [language, setLanguage] = useState('en');
  const [contentLength, setContentLength] = useState('standard');
  const [includeImage, setIncludeImage] = useState(true);
  const [category, setCategory] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editMessage, setEditMessage] = useState('');
  const [editMediaUrl, setEditMediaUrl] = useState('');
  const [scheduleValues, setScheduleValues] = useState({});
  const [publishPlatforms, setPublishPlatforms] = useState({});
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const selectedPage = useMemo(
    () => pages.find((page) => String(page.id) === String(pageId)),
    [pages, pageId],
  );

  const loadPageData = useCallback(async (targetPageId) => {
    if (!targetPageId) return;
    setError('');
    const [configResponse, postsResponse, scheduledResponse, historyResponse] = await Promise.all([
      api.get('/posts/automation-config', { params: { page_id: targetPageId } }),
      api.get('/posts/', { params: { page_id: targetPageId } }),
      api.get('/posts/scheduled', { params: { page_id: targetPageId } }),
      api.get('/posts/history', { params: { page_id: targetPageId } }),
    ]);
    setConfig(configResponse.data);
    setConfigForm({
      enabled: configResponse.data.enabled,
      frequency: configResponse.data.frequency,
      generation_time: configResponse.data.generation_time,
      timezone: configResponse.data.timezone,
      posts_per_cycle: configResponse.data.posts_per_cycle,
      languages: configResponse.data.languages,
      tone: configResponse.data.tone,
      category_mode: configResponse.data.category_mode,
      categories: configResponse.data.categories.join(', '),
      approval_required: configResponse.data.approval_required,
      brand_context: configResponse.data.brand_context,
      brand_profile_text: JSON.stringify(configResponse.data.brand_profile || {}, null, 2),
      default_content_length: configResponse.data.default_content_length || 'standard',
    });
    setContentLength(configResponse.data.default_content_length || 'standard');
    setPosts(postsResponse.data.filter((post) => post.is_ai_generated));
    setScheduled(scheduledResponse.data);
    setHistory(historyResponse.data);
  }, []);

  const refreshPosts = useCallback(async () => {
    if (!pageId) return;
    const response = await api.get('/posts/', { params: { page_id: pageId } });
    setPosts(response.data.filter((post) => post.is_ai_generated));
  }, [pageId]);

  const loadPages = useCallback(async () => {
    try {
      const response = await api.get('/pages/');
      const availablePages = response.data.filter(
        (page) => page.is_connected && page.token_status !== 'simulated',
      );
      setPages(availablePages);
      const initialPageId = String(availablePages[0]?.id || '');
      setPageId(initialPageId);
      if (initialPageId) await loadPageData(initialPageId);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setLoading(false);
    }
  }, [loadPageData]);

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  useEffect(() => {
    if (!posts.some((post) => ['queued', 'in_progress'].includes(post.media_status))) {
      return undefined;
    }
    const interval = setInterval(() => {
      void refreshPosts().catch((requestError) => setError(errorText(requestError)));
    }, 5000);
    return () => clearInterval(interval);
  }, [posts, refreshPosts]);

  const runAction = async (key, action, successMessage) => {
    setWorking(key);
    setError('');
    setNotice('');
    try {
      await action();
      if (pageId) await loadPageData(pageId);
      if (successMessage) setNotice(successMessage);
      return true;
    } catch (requestError) {
      setError(errorText(requestError));
      return false;
    } finally {
      setWorking('');
    }
  };

  const saveConfig = (event) => {
    event.preventDefault();
    let brandProfile;
    try {
      brandProfile = JSON.parse(configForm.brand_profile_text);
    } catch {
      setError('Brand profile must be valid JSON before it can be saved.');
      return;
    }
    if (!brandProfile || typeof brandProfile !== 'object' || Array.isArray(brandProfile)) {
      setError('Brand profile must be a JSON object.');
      return;
    }
    const configValues = { ...configForm };
    const categories = configValues.categories;
    delete configValues.categories;
    delete configValues.brand_profile_text;
    const payload = {
      ...configValues,
      brand_profile: brandProfile,
      posts_per_cycle: Number(configForm.posts_per_cycle),
      categories: categories
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    };
    void runAction(
      'config',
      async () => {
        const response = await api.put('/posts/automation-config', payload, { params: { page_id: pageId } });
        setConfig(response.data);
        setConfigForm({
          ...response.data,
          categories: response.data.categories.join(', '),
          brand_profile_text: JSON.stringify(response.data.brand_profile || {}, null, 2),
        });
        setContentLength(response.data.default_content_length || 'standard');
      },
      'Content automation settings saved.',
    );
  };

  const generateNow = (event) => {
    event.preventDefault();
    if (!pageId) return;
    const requestId = globalThis.crypto?.randomUUID?.() || `manual-${Date.now()}`;
    void runAction(
      'generate',
      () => api.post('/posts/generate-draft', {
        page_id: Number(pageId),
        topic: topic.trim() || category || undefined,
        category: category || undefined,
        language,
        content_length: contentLength,
        include_image: includeImage,
        tone: config?.tone || 'professional and engaging',
        request_id: requestId,
      }),
      'Draft generated and added to the approval queue.',
    ).then((succeeded) => { if (succeeded) setTab('drafts'); });
  };

  const saveDraft = (postId) => runAction(
    `save-${postId}`,
    () => api.put(`/posts/${postId}/draft`, {
      message: editMessage,
      media_url: editMediaUrl || null,
    }),
    'Draft changes saved.',
  ).then((succeeded) => { if (succeeded) setEditingId(null); });

  const regenerate = (post) => runAction(
    `regenerate-${post.id}`,
    () => api.post(`/posts/${post.id}/regenerate`),
    'Alternative draft generated.',
  );

  const regenerateMedia = (postId) => runAction(
    `regenerate-media-${postId}`,
    () => api.post(`/posts/${postId}/regenerate-media`),
    'Image generation queued. You can keep reviewing the caption.',
  );

  const approve = (postId) => runAction(
    `approve-${postId}`,
    () => api.post(`/posts/${postId}/approve`),
    'Draft approved. It has not been published.',
  );

  const reject = (postId) => {
    const reason = window.prompt('Optional reason for rejecting this draft:', '');
    if (reason === null) return;
    return runAction(
      `reject-${postId}`,
      () => api.post(`/posts/${postId}/reject`, { reason: reason.trim() || null }),
      'Draft rejected and recorded in history.',
    );
  };

  const schedule = (postId) => {
    const localDateTime = scheduleValues[postId];
    if (!localDateTime) {
      setError('Choose a future date and time before scheduling.');
      return;
    }
    const instant = new Date(localDateTime);
    if (Number.isNaN(instant.getTime()) || instant <= new Date()) {
      setError('Scheduled time must be in the future.');
      return;
    }
    return runAction(
      `schedule-${postId}`,
      () => api.post(`/posts/${postId}/schedule`, { scheduled_for: instant.toISOString() }),
      'Post scheduled. It will not be sent to Facebook automatically.',
    );
  };

  const cancelSchedule = (postId) => runAction(
    `cancel-${postId}`,
    () => api.delete(`/posts/${postId}/schedule`),
    'Schedule cancelled. The approved content remains saved.',
  );

  const selectedPublishPlatforms = (post) => {
    if (publishPlatforms[post.id]) return publishPlatforms[post.id];
    if (['partially_published', 'failed', 'published'].includes(post.status)) {
      return ['facebook', 'instagram'].filter((platform) => {
        const platformStatus = post[`${platform}_status`];
        if (platformStatus === 'published') return false;
        if (platformStatus === 'failed') return true;
        return post.status !== 'failed' && platformStatus === 'not_requested';
      }).filter((platform) => (
        platform !== 'instagram'
        || (selectedPage?.instagram_business_account_id && post.media_url)
      ));
    }
    return [
      ...(post.facebook_status === 'published' ? [] : ['facebook']),
      ...(selectedPage?.instagram_business_account_id && post.media_url && post.instagram_status !== 'published'
        ? ['instagram']
        : []),
    ];
  };

  const publishManually = (post) => {
    if (simulationMode) {
      setError('Live publishing is disabled while simulation mode is on.');
      return;
    }
    const platforms = selectedPublishPlatforms(post);
    if (!platforms.length) {
      setError('Select at least one platform that has not already published this post.');
      return;
    }
    const confirmed = window.confirm(
      `Publish this approved post to ${platforms.join(' and ')} now? This is a real public post.`,
    );
    if (!confirmed) return;
    return runAction(
      `publish-${post.id}`,
      () => api.post(`/posts/${post.id}/publish`, {
        edited_message: post.message,
        media_url: post.media_url,
        confirm_publish: true,
        platforms,
      }),
      'Platform publication status updated.',
    ).then((succeeded) => {
      if (succeeded) {
        setPublishPlatforms((current) => {
          const next = { ...current };
          delete next[post.id];
          return next;
        });
      }
    });
  };

  const beginEdit = (post) => {
    setEditingId(post.id);
    setEditMessage(post.message || '');
    setEditMediaUrl(post.media_url || '');
  };

  const dateLabel = (value) => (value ? new Date(value).toLocaleString() : '—');
  const mediaSource = (mediaUrl) => {
    if (!mediaUrl) return '';
    try {
      return new URL(mediaUrl, api.defaults.baseURL).toString();
    } catch {
      return '';
    }
  };

  const uploadMedia = async (postId, event) => {
    const [file] = event.target.files || [];
    if (!file) return;
    setWorking(`upload-media-${postId}`);
    setError('');
    setNotice('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post('/posts/media/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setEditMediaUrl(response.data.media_url);
      setNotice('Image uploaded. Save the draft to attach it.');
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setWorking('');
      event.target.value = '';
    }
  };

  const postCard = (post, mode = 'draft') => {
    const isEditing = editingId === post.id;
    const pending = working.endsWith(`-${post.id}`);
    return (
      <article key={post.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">
                {post.content_category || 'General'}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                {post.content_language || 'en'}
              </span>
              <span className="rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold capitalize text-violet-700">
                {post.content_length || 'standard'}
              </span>
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold capitalize text-amber-800">
                {post.status}
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {selectedPage?.name || 'Facebook Page'} · Generated {dateLabel(post.created_at)}
            </p>
            {post.topic && <p className="mt-1 text-xs text-slate-500">Topic: {post.topic}</p>}
          </div>
          {post.scheduled_for && (
            <p className="flex items-center gap-1 text-xs font-medium text-sky-700">
              <CalendarClock className="h-4 w-4" /> {dateLabel(post.scheduled_for)}
            </p>
          )}
        </div>
        {isEditing ? (
          <div className="space-y-3">
            <textarea
              value={editMessage}
              onChange={(event) => setEditMessage(event.target.value)}
              rows={7}
              maxLength={63206}
              className="w-full rounded-xl border border-slate-300 p-3 text-sm leading-6"
              aria-label="Edit generated caption"
            />
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold text-slate-700">
                <ImagePlus className="h-4 w-4" /> Upload image
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  className="sr-only"
                  onChange={(event) => uploadMedia(post.id, event)}
                />
              </label>
              <span className="text-xs text-slate-500">PNG or JPEG, up to 10 MB</span>
              {editMediaUrl && (
                <button type="button" onClick={() => setEditMediaUrl('')} className="text-xs text-rose-700">
                  Remove image
                </button>
              )}
            </div>
            {editMediaUrl && <img src={mediaSource(editMediaUrl)} alt="Selected post visual" className="max-h-64 rounded-xl border object-contain" />}
          </div>
        ) : (
          <div className="space-y-4">
            {mode !== 'draft' && (
              <p className="text-xs text-slate-600">
                Platform status: Facebook {post.facebook_status || 'not requested'} · Instagram {post.instagram_status || 'not requested'}
                {post.instagram_permalink_url && <> · <a className="text-blue-700 underline" href={post.instagram_permalink_url} target="_blank" rel="noreferrer">View Instagram post</a></>}
              </p>
            )}
            <p className="whitespace-pre-line text-sm leading-6 text-slate-800">{post.message}</p>
            {post.media_brief && (
              <p className="text-xs text-slate-500"><strong>Visual concept:</strong> {post.media_brief}</p>
            )}
            {post.media_url && (
              <img src={mediaSource(post.media_url)} alt="Visual attached to this post draft" className="max-h-96 w-full rounded-xl border object-contain" />
            )}
            {['queued', 'in_progress'].includes(post.media_status) && (
              <p className="flex items-center gap-2 rounded-lg bg-indigo-50 p-2 text-xs text-indigo-800" role="status">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Image is generating in the background. You can review or publish this caption without waiting.
              </p>
            )}
            {post.media_status === 'failed' && (
              <p className="rounded-lg bg-rose-50 p-2 text-xs text-rose-800">
                Image generation failed. The caption is still available; publishing without an image is allowed.
              </p>
            )}
            {post.missing_facts?.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <strong>Administrator fact check:</strong>
                <ul className="mt-1 list-inside list-disc">{post.missing_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
              </div>
            )}
            {!post.media_url && (
              <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
                No image attached. Images are optional; text-only posts can be published.
              </p>
            )}
            {post.media_warning && <p className="text-xs text-rose-700">{post.media_warning}</p>}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
          {mode === 'draft' && (isEditing ? (
            <>
              <button onClick={() => setEditingId(null)} className="rounded-lg border px-3 py-2 text-xs">Cancel</button>
              <button
                onClick={() => saveDraft(post.id)}
                disabled={!editMessage.trim() || pending}
                className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {pending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save edit
              </button>
            </>
          ) : (
            <>
              <button onClick={() => beginEdit(post)} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs">
                <Pencil className="h-4 w-4" /> Edit
              </button>
              <button
                onClick={() => regenerate(post)}
                disabled={working === `regenerate-${post.id}`}
                className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs disabled:opacity-50"
              >
                <RotateCw className={`h-4 w-4 ${working === `regenerate-${post.id}` ? 'animate-spin' : ''}`} /> Regenerate
              </button>
              {post.media_brief && (
                <button
                  onClick={() => regenerateMedia(post.id)}
                  disabled={['queued', 'in_progress'].includes(post.media_status) || working === `regenerate-media-${post.id}`}
                  className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs disabled:opacity-50"
                  title="Generate a fresh image in the background"
                >
                  <ImagePlus className="h-4 w-4" /> Regenerate image
                </button>
              )}
              <button onClick={() => approve(post.id)} disabled={pending} className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
                <Check className="h-4 w-4" /> Approve
              </button>
              <button onClick={() => reject(post.id)} disabled={pending} className="flex items-center gap-1 rounded-lg border border-rose-200 px-3 py-2 text-xs text-rose-700 disabled:opacity-50">
                <ThumbsDown className="h-4 w-4" /> Reject
              </button>
            </>
          ))}
          {mode === 'scheduled' && (
            <>
              <fieldset className="flex flex-wrap gap-3 text-xs">
                <legend className="sr-only">Select publishing platforms</legend>
                {['facebook', ...(selectedPage?.instagram_business_account_id ? ['instagram'] : [])].map((platform) => {
                  const chosen = selectedPublishPlatforms(post).includes(platform);
                  const alreadyPublished = post[`${platform}_status`] === 'published';
                  const unavailableInstagram = platform === 'instagram' && !post.media_url;
                  return (
                    <label key={platform} className="flex items-center gap-1 capitalize text-slate-700">
                      <input
                        type="checkbox"
                        checked={chosen}
                        disabled={alreadyPublished || unavailableInstagram}
                        onChange={(event) => setPublishPlatforms((current) => {
                          const currentSelection = selectedPublishPlatforms(post);
                          const nextSelection = event.target.checked
                            ? [...currentSelection, platform]
                            : currentSelection.filter((item) => item !== platform);
                          return { ...current, [post.id]: nextSelection };
                        })}
                      />
                      {platform} {alreadyPublished ? '(published)' : ''}
                    </label>
                  );
                })}
                {!selectedPage?.instagram_business_account_id && (
                  <span className="text-slate-500">Instagram account not connected</span>
                )}
              </fieldset>
              <button onClick={() => cancelSchedule(post.id)} disabled={pending} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs disabled:opacity-50">
                <X className="h-4 w-4" /> Cancel schedule
              </button>
              <button
                onClick={() => publishManually(post)}
                disabled={simulationMode || pending}
                title={simulationMode ? 'Turn simulation off to enable manual live publishing' : 'Publish only after explicit confirmation'}
                className="flex items-center gap-1 rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Send className="h-4 w-4" /> Publish manually
              </button>
            </>
          )}
          {(mode === 'approved' || mode === 'retry') && (
            <div className="flex flex-wrap items-center gap-2">
              {mode === 'approved' && (
                <>
                  <input
                    type="datetime-local"
                    value={scheduleValues[post.id] || ''}
                    onChange={(event) => setScheduleValues((current) => ({ ...current, [post.id]: event.target.value }))}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-xs"
                    aria-label="Schedule publication time"
                  />
                  <button onClick={() => schedule(post.id)} disabled={pending} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs disabled:opacity-50">
                    <CalendarClock className="h-4 w-4" /> Schedule
                  </button>
                </>
              )}
              <fieldset className="flex flex-wrap gap-3 text-xs">
                <legend className="sr-only">Select publishing platforms</legend>
                {['facebook', ...(selectedPage?.instagram_business_account_id ? ['instagram'] : [])].map((platform) => {
                  const chosen = selectedPublishPlatforms(post).includes(platform);
                  const alreadyPublished = post[`${platform}_status`] === 'published';
                  const unavailableInstagram = platform === 'instagram' && !post.media_url;
                  return (
                    <label key={platform} className="flex items-center gap-1 capitalize text-slate-700">
                      <input
                        type="checkbox"
                        checked={chosen}
                        disabled={alreadyPublished || unavailableInstagram}
                        onChange={(event) => setPublishPlatforms((current) => {
                          const currentSelection = selectedPublishPlatforms(post);
                          const nextSelection = event.target.checked
                            ? [...currentSelection, platform]
                            : currentSelection.filter((item) => item !== platform);
                          return { ...current, [post.id]: nextSelection };
                        })}
                      />
                      {platform} {alreadyPublished ? '(published)' : ''}
                    </label>
                  );
                })}
                {!selectedPage?.instagram_business_account_id && (
                  <span className="text-slate-500">Instagram account not connected</span>
                )}
              </fieldset>
              <button
                onClick={() => publishManually(post)}
                disabled={simulationMode || pending}
                title={simulationMode ? 'Turn simulation off to enable manual live publishing' : 'Publish only after explicit confirmation'}
                className="flex items-center gap-1 rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Send className="h-4 w-4" /> Publish manually
              </button>
            </div>
          )}
        </div>
      </article>
    );
  };

  if (loading) {
    return <div className="flex items-center justify-center gap-2 p-16 text-sm text-slate-500"><LoaderCircle className="h-5 w-5 animate-spin" /> Loading AI content tools…</div>;
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">AI Content Automation</h1>
          <p className="mt-1 text-sm text-slate-500">Gemini-generated drafts require administrator review. Scheduling never publishes automatically.</p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="content-page" className="text-xs font-semibold text-slate-600">Facebook Page</label>
          <select
            id="content-page"
            value={pageId}
            onChange={(event) => {
              const nextPageId = event.target.value;
              setPageId(nextPageId);
              void loadPageData(nextPageId).catch((requestError) => setError(errorText(requestError)));
            }}
            className="max-w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            {pages.length === 0 && <option value="">No connected Pages</option>}
            {pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
          </select>
          <button onClick={() => loadPageData(pageId).catch((requestError) => setError(errorText(requestError)))} className="rounded-lg border p-2 text-slate-600" aria-label="Refresh content"><RefreshCw className="h-4 w-4" /></button>
        </div>
      </header>

      {simulationMode && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Simulation mode is on. Content generation and scheduling are available; manual live publishing is disabled.
        </div>
      )}
      {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
      {!pages.length && <div className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">Connect a Facebook Page to configure content generation.</div>}

      {pageId && configForm && (
        <>
          <nav className="flex flex-wrap gap-2 border-b border-slate-200 pb-2" aria-label="AI content sections">
            {TABS.map((item) => (
              <button key={item.id} onClick={() => setTab(item.id)} className={`rounded-lg px-3 py-2 text-sm font-semibold ${tab === item.id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
                {item.label}
              </button>
            ))}
          </nav>

          {tab === 'generate' && (
            <div className="grid gap-5 lg:grid-cols-2">
              <form onSubmit={generateNow} className="rounded-2xl border bg-white p-5 shadow-sm space-y-4">
                <div className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-indigo-600" /><h2 className="font-bold">Generate a draft now</h2></div>
                <label className="block text-xs font-semibold text-slate-600">Topic (optional)
                  <input value={topic} onChange={(event) => setTopic(event.target.value)} maxLength={500} placeholder="e.g. practical uses of AI in local businesses" className="mt-1 w-full rounded-lg border p-2.5 text-sm" />
                </label>
                <label className="block text-xs font-semibold text-slate-600">Category
                  <select value={category} onChange={(event) => setCategory(event.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2.5 text-sm">
                    <option value="">Rotate category</option>
                    {(config?.categories || []).map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label className="block text-xs font-semibold text-slate-600">Language
                  <select value={language} onChange={(event) => setLanguage(event.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2.5 text-sm">
                    <option value="en">English</option><option value="ne">Nepali</option><option value="bilingual">Bilingual</option>
                  </select>
                </label>
                <label className="block text-xs font-semibold text-slate-600">Caption length
                  <select value={contentLength} onChange={(event) => setContentLength(event.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2.5 text-sm">
                    <option value="short">Short · 60–100 words</option>
                    <option value="standard">Standard · 120–200 words</option>
                    <option value="detailed">Detailed · 200–300 words</option>
                    <option value="storytelling">Storytelling · 180–350 words</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={includeImage} onChange={(event) => setIncludeImage(event.target.checked)} />
                  Generate an image with this draft
                </label>
                {!includeImage && <p className="text-xs text-slate-500">This will be a text-only post. Images are optional.</p>}
                <button disabled={working === 'generate'} className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                  {working === 'generate' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {working === 'generate' ? 'Generating…' : 'Generate Now'}
                </button>
              </form>

              <form onSubmit={saveConfig} className="rounded-2xl border bg-white p-5 shadow-sm space-y-4">
                <div className="flex items-center gap-2"><Settings2 className="h-5 w-5 text-slate-600" /><h2 className="font-bold">Content automation settings</h2></div>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={configForm.enabled} onChange={(event) => setConfigForm({ ...configForm, enabled: event.target.checked })} /> Enable scheduled draft generation</label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-xs font-semibold text-slate-600">Frequency
                    <select value={configForm.frequency} onChange={(event) => setConfigForm({ ...configForm, frequency: event.target.value })} className="mt-1 w-full rounded-lg border bg-white p-2 text-sm"><option value="daily">Daily</option></select>
                  </label>
                  <label className="text-xs font-semibold text-slate-600">Generation time
                    <input type="time" value={configForm.generation_time} onChange={(event) => setConfigForm({ ...configForm, generation_time: event.target.value })} className="mt-1 w-full rounded-lg border p-2 text-sm" />
                  </label>
                  <label className="text-xs font-semibold text-slate-600">Timezone
                    <input value={configForm.timezone} onChange={(event) => setConfigForm({ ...configForm, timezone: event.target.value })} className="mt-1 w-full rounded-lg border p-2 text-sm" />
                  </label>
                  <label className="text-xs font-semibold text-slate-600">Posts per cycle
                    <input type="number" min="1" max="5" value={configForm.posts_per_cycle} onChange={(event) => setConfigForm({ ...configForm, posts_per_cycle: event.target.value })} className="mt-1 w-full rounded-lg border p-2 text-sm" />
                  </label>
                </div>
                <label className="block text-xs font-semibold text-slate-600">Brand tone
                  <input value={configForm.tone} onChange={(event) => setConfigForm({ ...configForm, tone: event.target.value })} maxLength={80} className="mt-1 w-full rounded-lg border p-2 text-sm" />
                </label>
                <label className="block text-xs font-semibold text-slate-600">Default caption length
                  <select value={configForm.default_content_length} onChange={(event) => setConfigForm({ ...configForm, default_content_length: event.target.value })} className="mt-1 w-full rounded-lg border bg-white p-2 text-sm">
                    <option value="short">Short · 60–100 words</option>
                    <option value="standard">Standard · 120–200 words</option>
                    <option value="detailed">Detailed · 200–300 words</option>
                    <option value="storytelling">Storytelling · 180–350 words</option>
                  </select>
                </label>
                <fieldset className="space-y-2">
                  <legend className="text-xs font-semibold text-slate-600">Generation languages</legend>
                  {['en', 'ne', 'bilingual'].map((value) => (
                    <label key={value} className="mr-3 inline-flex items-center gap-1 text-xs">
                      <input
                        type="checkbox"
                        checked={configForm.languages.includes(value)}
                        onChange={(event) => setConfigForm({
                          ...configForm,
                          languages: event.target.checked
                            ? [...configForm.languages, value]
                            : configForm.languages.filter((languageValue) => languageValue !== value),
                        })}
                      />
                      {value === 'en' ? 'English' : value === 'ne' ? 'Nepali' : 'Bilingual'}
                    </label>
                  ))}
                </fieldset>
                <label className="block text-xs font-semibold text-slate-600">Category selection
                  <select value={configForm.category_mode} onChange={(event) => setConfigForm({ ...configForm, category_mode: event.target.value })} className="mt-1 w-full rounded-lg border bg-white p-2 text-sm">
                    <option value="rotating">Rotate categories</option><option value="custom">Custom category list</option>
                  </select>
                </label>
                <label className="block text-xs font-semibold text-slate-600">Categories (comma-separated)
                  <textarea rows={3} value={configForm.categories} onChange={(event) => setConfigForm({ ...configForm, categories: event.target.value })} className="mt-1 w-full rounded-lg border p-2 text-sm" />
                </label>
                <label className="block text-xs font-semibold text-slate-600">Brand information
                  <textarea rows={5} value={configForm.brand_context} onChange={(event) => setConfigForm({ ...configForm, brand_context: event.target.value })} className="mt-1 w-full rounded-lg border p-2 text-sm" />
                </label>
                <label className="block text-xs font-semibold text-slate-600">Structured brand knowledge (JSON)
                  <textarea rows={14} value={configForm.brand_profile_text} onChange={(event) => setConfigForm({ ...configForm, brand_profile_text: event.target.value })} className="mt-1 w-full rounded-lg border p-2 font-mono text-xs" />
                  <span className="mt-1 block font-normal text-slate-500">Add only verified product descriptions and approved features. Empty product records are flagged for review.</span>
                </label>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked disabled /> Administrator approval required</label>
                <p className="rounded-lg bg-slate-50 p-2 text-xs text-slate-600">Approval is required and automatic Facebook publishing is fixed off for this development phase.</p>
                <button disabled={working === 'config'} className="flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                  {working === 'config' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save settings
                </button>
              </form>
            </div>
          )}

          {tab === 'drafts' && (
            <section className="space-y-4">
              <h2 className="font-bold text-slate-900">Generated drafts awaiting review ({posts.filter((post) => post.status === 'draft').length})</h2>
              {posts.some((post) => post.status === 'draft') ? posts.filter((post) => post.status === 'draft').map((post) => postCard(post)) : <div className="rounded-2xl border bg-white p-10 text-center text-sm text-slate-500">No drafts yet. Use Generate Now or wait for the next scheduled cycle.</div>}
            </section>
          )}

          {tab === 'scheduled' && (
            <section className="space-y-4">
              <h2 className="font-bold text-slate-900">Upcoming scheduled content ({scheduled.length})</h2>
              <p className="text-xs text-slate-500">These dates are saved for planning only; the scheduler will not publish them to Facebook.</p>
              {scheduled.length ? scheduled.map((post) => postCard(post, 'scheduled')) : <div className="rounded-2xl border bg-white p-10 text-center text-sm text-slate-500">No scheduled posts.</div>}
              <h3 className="pt-4 font-bold text-slate-900">Approved and ready for publishing</h3>
              {posts.filter((post) => post.status === 'approved').map((post) => postCard(post, 'approved'))}
              {posts.filter((post) => (
                ['partially_published', 'failed'].includes(post.status)
                || (
                  post.status === 'published'
                  && post.is_ai_generated
                  && post.approved_at
                  && (
                    post.facebook_status !== 'published'
                    || (
                      selectedPage?.instagram_business_account_id
                      && post.media_url
                      && post.instagram_status !== 'published'
                    )
                  )
                )
              )).map((post) => postCard(post, 'retry'))}
            </section>
          )}

          {tab === 'history' && (
            <section className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-2xl border bg-white p-5">
                <h2 className="mb-3 flex items-center gap-2 font-bold"><Clock3 className="h-4 w-4" /> Generation jobs</h2>
                {history.generation_runs.length ? <ul className="space-y-3">{history.generation_runs.map((run) => (
                  <li key={run.id} className="border-b pb-3 text-sm">
                    <div className="flex justify-between gap-3"><strong>{run.content_category || run.topic || 'Content generation'}</strong><span className="capitalize text-slate-500">{run.status}</span></div>
                    <p className="mt-1 text-xs text-slate-500">{run.source} · {dateLabel(run.started_at)}</p>
                    {run.error_message && <p className="mt-1 text-xs text-rose-700">{run.error_message}</p>}
                    {run.post_id && <p className="mt-1 text-xs text-emerald-700">Draft #{run.post_id}</p>}
                  </li>
                ))}</ul> : <p className="text-sm text-slate-500">No generation history yet.</p>}
              </div>
              <div className="rounded-2xl border bg-white p-5">
                <h2 className="mb-3 flex items-center gap-2 font-bold"><History className="h-4 w-4" /> Draft and approval history</h2>
                {history.content_versions.length ? <ul className="space-y-3">{history.content_versions.map((version) => (
                  <li key={version.id} className="border-b pb-3">
                    <div className="flex justify-between gap-3 text-sm"><strong className="capitalize">{version.event_type.replaceAll('_', ' ')}</strong><span className="text-xs text-slate-500">{dateLabel(version.created_at)}</span></div>
                    <p className="mt-1 line-clamp-3 whitespace-pre-line text-xs text-slate-600">{version.message}</p>
                    {version.reason && <p className="mt-1 text-xs text-slate-500">Note: {version.reason}</p>}
                  </li>
                ))}</ul> : <p className="text-sm text-slate-500">No content changes recorded yet.</p>}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
