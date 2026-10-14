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
  Send, 
  Trash2, 
  Edit3, 
  CheckCircle2, 
  Plus, 
  Clock 
} from 'lucide-react';
import api from '../api';

export default function PostMonitor() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all'); // 'all', 'drafts', 'published'
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [publishingId, setPublishingId] = useState(null);

  // Post Generator Form
  const [postTopic, setPostTopic] = useState('चाडपर्वको विशेष अफर र नयाँ सामानहरू');
  const [postLang, setPostLang] = useState('ne');
  const [postTone, setPostTone] = useState('promotional');
  const [autoPublishDirect, setAutoPublishDirect] = useState(false);

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
  }, []);

  const handleToggleMonitoring = async (postId) => {
    try {
      await api.post(`/posts/${postId}/toggle-monitoring`);
      await fetchPosts();
    } catch (err) {
      alert('Failed to toggle post monitoring: ' + err.message);
    }
  };

  const handleGeneratePost = async (e) => {
    e.preventDefault();
    setGenerating(true);
    try {
      await api.post('/posts/generate-draft', {
        page_id: 1, // Default connected page
        topic: postTopic,
        language: postLang,
        tone: postTone,
        auto_publish: autoPublishDirect
      });
      setShowGenerateModal(false);
      await fetchPosts();
      setActiveTab(autoPublishDirect ? 'published' : 'drafts');
    } catch (err) {
      alert('Generation failed: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handlePublishDraft = async (postId, currentMessage, currentMedia) => {
    const confirmed = confirm('Publish this AI-generated post live to your Facebook Page now?');
    if (!confirmed) return;
    setPublishingId(postId);
    try {
      await api.post(`/posts/${postId}/publish`, {
        edited_message: currentMessage,
        media_url: currentMedia
      });
      await fetchPosts();
    } catch (err) {
      alert('Publishing failed: ' + err.message);
    } finally {
      setPublishingId(null);
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
    if (activeTab === 'published') return p.status !== 'draft';
    return true;
  });

  const draftCount = posts.filter((p) => p.status === 'draft').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-xl font-bold text-slate-900">Facebook Posts & Content Creator</h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200">
              Daily Automation Engine
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Automated daily content generation, bilingual captions (नेपाली / EN), and live post engagement tracking.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowGenerateModal(true)}
            className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
          >
            <Sparkles className="w-4 h-4" />
            <span>Generate Daily AI Post</span>
          </button>

          <button
            onClick={fetchPosts}
            disabled={loading}
            className="px-3 py-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs Filter */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === 'all' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          All Posts ({posts.length})
        </button>
        <button
          onClick={() => setActiveTab('drafts')}
          className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
            activeTab === 'drafts' ? 'bg-amber-500 text-white' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Clock className="w-3 h-3" />
          <span>AI Post Drafts ({draftCount})</span>
        </button>
        <button
          onClick={() => setActiveTab('published')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === 'published' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Published to Facebook ({posts.length - draftCount})
        </button>
      </div>

      {/* Posts Grid */}
      {loading && posts.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
          <p className="text-sm">Loading posts catalogue...</p>
        </div>
      ) : filteredPosts.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-3">
          <Newspaper className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="font-bold text-slate-800">No Posts in this section</h3>
          <p className="text-xs text-slate-500">
            Click "Generate Daily AI Post" to create a new bilingual Facebook post draft.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredPosts.map((post) => {
            const isDraft = post.status === 'draft';
            const isPublishing = publishingId === post.id;

            return (
              <div
                key={post.id}
                className={`bg-white rounded-2xl border overflow-hidden shadow-xs hover:shadow-md transition-all flex flex-col justify-between ${
                  isDraft ? 'border-amber-300 ring-2 ring-amber-100' : 'border-slate-200'
                }`}
              >
                <div>
                  {/* Status Banner for Draft */}
                  {isDraft && (
                    <div className="bg-amber-500 text-white px-4 py-1.5 text-[11px] font-bold flex items-center justify-between">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" /> AI Post Draft (Pending Review)
                      </span>
                      <span>Ready to Publish</span>
                    </div>
                  )}

                  {post.media_url && (
                    <div className="h-48 w-full bg-slate-100 overflow-hidden relative">
                      <img
                        src={post.media_url}
                        alt="Post media"
                        className="w-full h-full object-cover"
                      />
                      {post.is_ai_generated && (
                        <span className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/70 text-white text-[10px] font-semibold backdrop-blur-xs flex items-center gap-1">
                          <Sparkles className="w-3 h-3 text-amber-400" /> AI Created
                        </span>
                      )}
                    </div>
                  )}

                  <div className="p-5 space-y-3">
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span className="font-mono text-[10px]">ID: {post.meta_post_id}</span>
                      <span>{new Date(post.created_at).toLocaleDateString()}</span>
                    </div>

                    <p className="text-sm text-slate-800 leading-relaxed font-normal whitespace-pre-line">
                      {post.message || 'No caption text.'}
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
                  {isDraft ? (
                    <div className="flex items-center justify-between w-full">
                      <button
                        onClick={() => handleDeletePost(post.id)}
                        className="text-rose-600 hover:text-rose-800 flex items-center gap-1 font-semibold"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Discard</span>
                      </button>

                      <button
                        onClick={() => handlePublishDraft(post.id, post.message, post.media_url)}
                        disabled={isPublishing}
                        className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-all shadow-xs flex items-center gap-1.5"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>{isPublishing ? 'Publishing...' : 'Publish to Facebook'}</span>
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center space-x-4">
                        <span className="flex items-center gap-1 font-semibold">
                          <ThumbsUp className="w-3.5 h-3.5 text-blue-600" /> {post.like_count}
                        </span>
                        <span className="flex items-center gap-1 font-semibold">
                          <MessageSquare className="w-3.5 h-3.5 text-indigo-600" /> {post.comment_count}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleToggleMonitoring(post.id)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors ${
                            post.is_monitored
                              ? 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                              : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
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
                            className="p-1 rounded-lg hover:bg-slate-200 text-slate-500 transition-colors"
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
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center space-x-2 text-indigo-600 font-bold text-lg">
              <Sparkles className="w-5 h-5" />
              <h3 className="text-slate-900">Generate Daily Facebook Post (Gemini AI)</h3>
            </div>
            <p className="text-xs text-slate-500">
              The AI will craft an engaging post caption with emojis, value propositions, call-to-actions, and relevant hashtags.
            </p>

            <form onSubmit={handleGeneratePost} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Topic or Product Focus</label>
                <input
                  type="text"
                  required
                  value={postTopic}
                  onChange={(e) => setPostTopic(e.target.value)}
                  placeholder="e.g. Festival Mega Sale, New Arrival Earbuds, Customer Weekend Tip..."
                  className="w-full p-2.5 bg-slate-50 rounded-xl border border-slate-300 text-sm focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Language</label>
                  <select
                    value={postLang}
                    onChange={(e) => setPostLang(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 rounded-xl border border-slate-300"
                  >
                    <option value="ne">नेपाली (Nepali)</option>
                    <option value="bilingual">Bilingual (English + Nepali)</option>
                    <option value="en">English Only</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Tone & Theme</label>
                  <select
                    value={postTone}
                    onChange={(e) => setPostTone(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 rounded-xl border border-slate-300"
                  >
                    <option value="promotional">Promotional & Offers</option>
                    <option value="festive">Festive & Greetings</option>
                    <option value="engagement">Question / Engagement Hook</option>
                    <option value="tips">Educational Tips</option>
                  </select>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoPublishDirect}
                    onChange={(e) => setAutoPublishDirect(e.target.checked)}
                    className="rounded-sm border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <span className="font-semibold text-slate-800 block text-xs">Publish Immediately to Facebook</span>
                    <span className="text-[11px] text-slate-500">
                      If unchecked, saves as a Draft so you can review before posting.
                    </span>
                  </div>
                </label>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowGenerateModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={generating}
                  className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
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
