import React, { useState, useEffect } from 'react';
import {
  Newspaper,
  ThumbsUp,
  MessageSquare,
  ExternalLink,
  RefreshCw,
  Eye,
  EyeOff,
  Sparkles,
  Trash2,
  Edit3,
  Clock,
  ImagePlus,
} from 'lucide-react';
import api from '../api';

export default function PostMonitor({ onNavigate }) {
  const [posts, setPosts] = useState([]);
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingPages, setLoadingPages] = useState(true);
  const [activeTab, setActiveTab] = useState('all'); // 'all', 'drafts', 'published'
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [editingDraftId, setEditingDraftId] = useState(null);
  const [draftMessage, setDraftMessage] = useState('');
  const [draftMediaUrl, setDraftMediaUrl] = useState('');
  const [savingDraft, setSavingDraft] = useState(false);
  const [syncingCommentsId, setSyncingCommentsId] = useState(null);

  // Post Generator Form
  const [selectedPageId, setSelectedPageId] = useState('');
  const [postTopic, setPostTopic] = useState('चाडपर्वको विशेष अफर र नयाँ सामानहरू');
  const [postLang, setPostLang] = useState('ne');
  const [contentLength, setContentLength] = useState('standard');
  const [postTone, setPostTone] = useState('promotional');

  const fetchPages = async () => {
    setLoadingPages(true);
    try {
      const res = await api.get('/pages/');
      const connectedPages = res.data.filter((page) => page.is_connected);
      setPages(connectedPages);
      setSelectedPageId((currentPageId) =>
        connectedPages.some((page) => String(page.id) === currentPageId)
          ? currentPageId
          : String(connectedPages[0]?.id || '')
      );
    } catch (err) {
      console.error('Failed to load connected Pages:', err);
      setPages([]);
      setSelectedPageId('');
    } finally {
      setLoadingPages(false);
    }
  };

  const fetchPosts = async () => {
    setLoading(true);
    try {
      const res = await api.get('/posts/');
      setPosts(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
    fetchPages();
  }, []);

  const handleToggleMonitoring = async (postId) => {
    try {
      await api.post(`/posts/${postId}/toggle-monitoring`);
      await fetchPosts();
    } catch (err) {
      alert('Failed to toggle post monitoring: ' + err.message);
    }
  };

  const handleSyncComments = async (post) => {
    setSyncingCommentsId(post.id);
    try {
      const response = await api.post(`/comments/sync-post/${post.id}`);
      alert(
        `${response.data.platform} comments: ${response.data.retrieved} retrieved, ` +
        `${response.data.new_comments_processed} new comments queued.`,
      );
    } catch (err) {
      alert(`Comment sync failed: ${err.message}`);
    } finally {
      setSyncingCommentsId(null);
    }
  };

  const handleGeneratePost = async (e) => {
    e.preventDefault();
    setGenerating(true);
    try {
      await api.post('/posts/generate-draft', {
        page_id: Number(selectedPageId),
        topic: postTopic,
        language: postLang,
        content_length: contentLength,
        tone: postTone,
      });
      setShowGenerateModal(false);
      await fetchPosts();
      setActiveTab('drafts');
    } catch (err) {
      alert('Generation failed: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleEditDraft = (post) => {
    setEditingDraftId(post.id);
    setDraftMessage(post.message || '');
    setDraftMediaUrl(post.media_url || '');
  };

  const handleSaveDraft = async (postId) => {
    setSavingDraft(true);
    try {
      await api.put(`/posts/${postId}/draft`, {
        message: draftMessage,
        media_url: draftMediaUrl || null,
      });
      setEditingDraftId(null);
      await fetchPosts();
    } catch (err) {
      alert('Failed to save draft: ' + err.message);
    } finally {
      setSavingDraft(false);
    }
  };

  const handleUploadDraftMedia = async (event) => {
    const [file] = event.target.files || [];
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post('/posts/media/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDraftMediaUrl(response.data.media_url);
    } catch (err) {
      alert('Image upload failed: ' + err.message);
    } finally {
      event.target.value = '';
    }
  };

  const mediaSource = (mediaUrl) => {
    if (!mediaUrl) return '';
    try {
      return new URL(mediaUrl, api.defaults.baseURL).toString();
    } catch {
      return '';
    }
  };

  const handleDeletePost = async (postId) => {
    if (!confirm('Are you sure you want to discard this post?')) return;
    try {
      await api.delete(`/posts/${postId}`);
      await fetchPosts();
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const filteredPosts = posts.filter((p) => {
    if (activeTab === 'drafts') return p.status === 'draft';
    if (activeTab === 'published') return p.status === 'published' && !p.is_simulated;
    return true;
  });

  const draftCount = posts.filter((p) => p.status === 'draft').length;
  const publishedCount = posts.filter((p) => p.status === 'published' && !p.is_simulated).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">
            Facebook Posts &amp; Content Creator
          </h1>
          <p className="mt-0.5 text-sm text-[#5b6475]">
            Daily bilingual captions (<span className="font-devanagari">नेपाली</span> / EN) and live engagement tracking.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowGenerateModal(true)}
            className="min-h-[44px] bg-[#1b2140] hover:bg-[#28315c] text-white rounded-[10px] px-4.5 text-sm font-semibold transition-colors flex items-center gap-2 cursor-pointer shadow-xs"
          >
            <Sparkles className="w-4 h-4 text-[#ffb84d]" />
            <span>Generate daily AI post</span>
          </button>

          <button
            onClick={fetchPosts}
            disabled={loading}
            className="min-h-[44px] px-4 rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] text-[#141a2e] text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      {/* Tabs Filter */}
      <div className="flex flex-wrap gap-2 text-sm font-semibold">
        <button
          onClick={() => setActiveTab('all')}
          className={`min-h-[40px] px-4 rounded-full transition-colors cursor-pointer ${
            activeTab === 'all'
              ? 'bg-[#1b2140] text-white'
              : 'bg-white border border-[#d5d9e6] text-[#3a4358] hover:bg-[#f4f5f9]'
          }`}
        >
          All posts ({posts.length})
        </button>
        <button
          onClick={() => setActiveTab('drafts')}
          className={`min-h-[40px] px-4 rounded-full transition-colors flex items-center gap-1.5 cursor-pointer ${
            activeTab === 'drafts'
              ? 'bg-[#1b2140] text-white'
              : 'bg-white border border-[#d5d9e6] text-[#3a4358] hover:bg-[#f4f5f9]'
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          <span>AI post drafts ({draftCount})</span>
        </button>
        <button
          onClick={() => setActiveTab('published')}
          className={`min-h-[40px] px-4 rounded-full transition-colors cursor-pointer ${
            activeTab === 'published'
              ? 'bg-[#1b2140] text-white'
              : 'bg-white border border-[#d5d9e6] text-[#3a4358] hover:bg-[#f4f5f9]'
          }`}
        >
          Published to Facebook ({publishedCount})
        </button>
      </div>

      {/* Posts Grid */}
      {loading && posts.length === 0 ? (
        <div className="p-16 text-center text-[#5b6475] bg-white rounded-2xl border border-[#e4e7ef]">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-[#1b2140]" />
          <p className="text-sm">Loading posts catalogue...</p>
        </div>
      ) : filteredPosts.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-2xl border border-[#e4e7ef] space-y-3">
          <Newspaper className="w-10 h-10 text-[#5b6475] mx-auto" />
          <h3 className="font-bold text-[#141a2e]">No Posts in this section</h3>
          <p className="text-xs text-[#5b6475]">
            Click "Generate daily AI post" to create a new bilingual Facebook post draft.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredPosts.map((post) => {
            const isDraft = post.status === 'draft';

            return (
              <div
                key={post.id}
                className="bg-white rounded-2xl border border-[#e4e7ef] overflow-hidden flex flex-col justify-between transition-shadow hover:shadow-xs"
              >
                <div>
                  {post.is_simulated && (
                    <div className="bg-[#fff8eb] border-b border-[#ffe3b8] px-4 py-2 text-xs font-semibold text-[#7a3f00]">
                      Simulation record — this post was not published to Facebook.
                    </div>
                  )}

                  {post.media_url ? (
                    <div className="h-48 w-full bg-[#f4f5f9] overflow-hidden relative border-b border-[#e4e7ef]">
                      <img
                        src={mediaSource(post.media_url)}
                        alt="Post media"
                        className="w-full h-full object-cover"
                      />
                      {post.is_ai_generated && (
                        <span className="absolute top-2.5 left-2.5 px-2.5 py-1 rounded-[8px] bg-[#1b2140]/90 text-white text-[11px] font-semibold backdrop-blur-xs flex items-center gap-1">
                          <Sparkles className="w-3 h-3 text-[#ffb84d]" />
                          {post.generation_source === 'local_fallback' ? 'Local template' : 'AI created'}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div className="h-28 bg-[#f4f5f9] border-b border-[#e4e7ef] flex items-center justify-center text-xs text-[#5b6475]">
                      No image attached
                    </div>
                  )}

                  <div className="p-5 space-y-3">
                    <div className="flex items-center justify-between text-xs text-[#5b6475]">
                      <span className="font-mono text-[11px] text-[#3a4358]">ID: {post.meta_post_id}</span>
                      <span>{new Date(post.created_at).toLocaleDateString()}</span>
                    </div>

                    {!isDraft && (
                      <p className="text-xs text-[#5b6475]">
                        Facebook: {post.facebook_status || 'not requested'} · Instagram: {post.instagram_status || 'not requested'}
                        {post.instagram_permalink_url && (
                          <> · <a href={post.instagram_permalink_url} target="_blank" rel="noreferrer" className="text-[#2f3fb8] hover:underline">Instagram post</a></>
                        )}
                      </p>
                    )}

                    {isDraft && editingDraftId === post.id ? (
                      <div className="space-y-2.5">
                        <label className="block text-xs font-semibold text-[#5b6475]" htmlFor={`draft-message-${post.id}`}>
                          Draft caption
                        </label>
                        <textarea
                          id={`draft-message-${post.id}`}
                          rows={6}
                          value={draftMessage}
                          onChange={(event) => setDraftMessage(event.target.value)}
                          className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-3 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
                        />
                        <label className="block text-xs font-semibold text-[#5b6475]" htmlFor={`draft-media-${post.id}`}>
                          <span className="flex items-center gap-1">
                            <ImagePlus className="h-4 w-4 text-[#5b6475]" /> Upload PNG or JPEG image (up to 10 MB)
                          </span>
                        </label>
                        <input
                          id={`draft-media-${post.id}`}
                          type="file"
                          accept="image/png,image/jpeg"
                          onChange={handleUploadDraftMedia}
                          className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2 text-xs text-[#141a2e]"
                        />
                        {draftMediaUrl && (
                          <img src={mediaSource(draftMediaUrl)} alt="Selected post visual" className="max-h-48 rounded-xl border border-[#e4e7ef] object-contain" />
                        )}
                        {draftMediaUrl && (
                          <button type="button" onClick={() => setDraftMediaUrl('')} className="text-xs font-semibold text-[#a31f1f] hover:underline cursor-pointer">
                            Remove selected image
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-sm text-[#141a2e] leading-relaxed whitespace-pre-line font-normal">
                          {post.message || 'No caption text.'}
                        </p>
                        {post.media_brief && (
                          <p className="text-xs text-[#5b6475]"><strong>Visual concept:</strong> {post.media_brief}</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-4 bg-white border-t border-[#eceef5] flex items-center justify-between text-xs text-[#5b6475]">
                  {isDraft ? (
                    <div className="flex items-center justify-between w-full">
                      {editingDraftId === post.id ? (
                        <>
                          <button
                            onClick={() => setEditingDraftId(null)}
                            className="text-xs font-semibold text-[#5b6475] hover:text-[#141a2e] cursor-pointer"
                          >
                            Cancel edit
                          </button>
                          <button
                            onClick={() => handleSaveDraft(post.id)}
                            disabled={savingDraft || !draftMessage.trim()}
                            className="px-4 py-1.5 bg-[#1b2140] hover:bg-[#28315c] disabled:opacity-50 text-white font-semibold rounded-[10px] text-xs cursor-pointer"
                          >
                            {savingDraft ? 'Saving...' : 'Save draft'}
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => handleDeletePost(post.id)}
                            className="text-[#a31f1f] hover:underline flex items-center gap-1 font-semibold cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Discard</span>
                          </button>
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleEditDraft(post)}
                              className="px-3.5 py-1.5 border border-[#d5d9e6] hover:bg-[#f4f5f9] text-[#141a2e] font-semibold rounded-[10px] text-xs flex items-center gap-1 cursor-pointer"
                            >
                              <Edit3 className="w-3.5 h-3.5 text-[#5b6475]" />
                              Edit
                            </button>
                            <button
                              onClick={() => onNavigate?.('content')}
                              className="px-4 py-1.5 bg-[#1b2140] hover:bg-[#28315c] text-white font-semibold rounded-[10px] text-xs cursor-pointer flex items-center gap-1.5"
                            >
                              <span>Review &amp; approve</span>
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center space-x-4">
                        <span className="flex items-center gap-1 text-[#5b6475]">
                          <ThumbsUp className="w-3.5 h-3.5 text-[#1b2140]" /> {post.like_count} likes
                        </span>
                        <span className="flex items-center gap-1 text-[#5b6475]">
                          <MessageSquare className="w-3.5 h-3.5 text-[#1b2140]" /> {post.comment_count} comments
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleSyncComments(post)}
                          disabled={syncingCommentsId === post.id}
                          className="px-3 py-1.5 rounded-[10px] border border-[#d5d9e6] hover:bg-[#f4f5f9] text-[#141a2e] disabled:opacity-50 text-xs font-semibold cursor-pointer"
                        >
                          {syncingCommentsId === post.id ? 'Syncing…' : 'Sync comments'}
                        </button>
                        <button
                          onClick={() => handleToggleMonitoring(post.id)}
                          className={`px-3 py-1.5 rounded-[10px] text-xs font-semibold flex items-center gap-1 transition-colors cursor-pointer ${
                            post.is_monitored
                              ? 'bg-[#dff5ea] text-[#0b6b4a]'
                              : 'bg-[#eceef5] text-[#3a4358]'
                          }`}
                        >
                          {post.is_monitored ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                          <span>{post.is_monitored ? 'Monitored' : 'Ignored'}</span>
                        </button>

                        {post.permalink_url && (
                          <a
                            href={post.permalink_url}
                            target="_blank"
                            rel="noreferrer"
                            className="p-1.5 rounded-[10px] border border-[#d5d9e6] hover:bg-[#f4f5f9] text-[#5b6475] transition-colors"
                            title="Open on Facebook"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Generate AI Post Modal */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-[#e4e7ef] max-w-lg w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-[#1b2140]" />
              <h3 className="text-lg font-bold text-[#141a2e]">Generate Facebook Post Draft</h3>
            </div>
            <p className="text-xs text-[#5b6475]">
              Generate a caption and save it as a draft for review. It will never publish immediately.
            </p>

            <form onSubmit={handleGeneratePost} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[#5b6475] mb-1.5" htmlFor="post-page">
                  Facebook Page
                </label>
                <select
                  id="post-page"
                  required
                  value={selectedPageId}
                  onChange={(e) => setSelectedPageId(e.target.value)}
                  disabled={loadingPages || pages.length === 0}
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loadingPages ? (
                    <option value="">Loading Pages...</option>
                  ) : pages.length === 0 ? (
                    <option value="">No connected Pages available</option>
                  ) : (
                    pages.map((page) => (
                      <option key={page.id} value={page.id}>
                        {page.name} ({page.meta_page_id})
                      </option>
                    ))
                  )}
                </select>
                {!loadingPages && pages.length === 0 && (
                  <p className="mt-1 text-[#a31f1f]">
                    Connect a Facebook Page before generating a post draft.
                  </p>
                )}
              </div>

              <div>
                <label className="block font-semibold text-[#5b6475] mb-1.5">Topic or Product Focus</label>
                <input
                  type="text"
                  required
                  value={postTopic}
                  onChange={(e) => setPostTopic(e.target.value)}
                  placeholder="e.g. Festival Mega Sale, New Arrival Earbuds..."
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-[#5b6475] mb-1.5">Language</label>
                  <select
                    value={postLang}
                    onChange={(e) => setPostLang(e.target.value)}
                    className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e]"
                  >
                    <option value="ne">नेपाली (Nepali)</option>
                    <option value="bilingual">Bilingual (English + Nepali)</option>
                    <option value="en">English Only</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-[#5b6475] mb-1.5">Tone &amp; Theme</label>
                  <select
                    value={postTone}
                    onChange={(e) => setPostTone(e.target.value)}
                    className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e]"
                  >
                    <option value="promotional">Promotional &amp; Offers</option>
                    <option value="festive">Festive &amp; Greetings</option>
                    <option value="engagement">Question / Engagement Hook</option>
                    <option value="tips">Educational Tips</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-[#5b6475] mb-1.5">Caption length</label>
                <select
                  value={contentLength}
                  onChange={(event) => setContentLength(event.target.value)}
                  className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e]"
                >
                  <option value="short">Short · 60–100 words</option>
                  <option value="standard">Standard · 120–200 words</option>
                  <option value="detailed">Detailed · 200–300 words</option>
                  <option value="storytelling">Storytelling · 180–350 words</option>
                </select>
              </div>

              <div className="p-3 bg-[#fff8eb] rounded-xl border border-[#ffe3b8] text-xs text-[#7a3f00]">
                Generated content is saved to drafts. Review it and edit any claims before publishing.
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowGenerateModal(false)}
                  className="px-4 py-2 rounded-[10px] border border-[#d5d9e6] text-[#5b6475] hover:text-[#141a2e] font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={generating || loadingPages || pages.length === 0 || !selectedPageId}
                  className="px-5 py-2 rounded-[10px] bg-[#1b2140] hover:bg-[#28315c] text-white font-bold flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#ffb84d]" />
                  <span>{generating ? 'Drafting Post...' : 'Generate Post'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
