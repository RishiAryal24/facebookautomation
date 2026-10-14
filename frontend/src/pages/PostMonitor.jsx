import React, { useState, useEffect } from 'react';
import { Newspaper, ThumbsUp, MessageSquare, ExternalLink, RefreshCw, Eye, EyeOff } from 'lucide-react';
import api from '../api';

export default function PostMonitor() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Facebook Posts Monitor</h2>
          <p className="text-xs text-slate-500 mt-1">
            Real-time feed monitoring and engagement tracking across connected Pages (ANNEX A §2.3).
          </p>
        </div>
        <button
          onClick={fetchPosts}
          disabled={loading}
          className="px-3.5 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Posts</span>
        </button>
      </div>

      {loading && posts.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
          <p className="text-sm">Loading Facebook posts...</p>
        </div>
      ) : posts.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-3">
          <Newspaper className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="font-bold text-slate-800">No Posts Retrieved</h3>
          <p className="text-xs text-slate-500">Click 'Sync Feed' in the Connected Pages tab to fetch posts.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {posts.map((post) => (
            <div
              key={post.id}
              className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between"
            >
              <div>
                {post.media_url && (
                  <div className="h-44 w-full bg-slate-100 overflow-hidden">
                    <img
                      src={post.media_url}
                      alt="Post media"
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}

                <div className="p-5 space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-mono text-[10px]">ID: {post.meta_post_id}</span>
                    <span>{new Date(post.created_at).toLocaleDateString()}</span>
                  </div>

                  <p className="text-sm text-slate-800 leading-relaxed font-normal">
                    {post.message || 'No caption text.'}
                  </p>
                </div>
              </div>

              <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
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
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
