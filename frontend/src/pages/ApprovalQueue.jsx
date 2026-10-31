import React, { useState, useEffect } from 'react';
import { 
  Check, 
  X, 
  RefreshCw, 
  Edit3, 
  Sparkles, 
  Send, 
  AlertTriangle,
  Languages,
  MessageCircle,
  ThumbsUp,
  ExternalLink
} from 'lucide-react';
import api from '../api';

export default function ApprovalQueue({ onQueueUpdated }) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editedText, setEditedText] = useState('');
  const [alsoLike, setAlsoLike] = useState(true);
  const [regeneratingId, setRegeneratingId] = useState(null);
  const [selectedTone, setSelectedTone] = useState('friendly');
  const [selectedLang, setSelectedLang] = useState('ne');
  const [processingId, setProcessingId] = useState(null);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await api.get('/comments/queue');
      setComments(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleApprove = async (commentId) => {
    setProcessingId(commentId);
    try {
      const payload = {
        edited_reply: editingId === commentId ? editedText : null,
        also_like: alsoLike,
      };
      await api.post(`/comments/${commentId}/approve`, payload);
      setEditingId(null);
      await fetchQueue();
      if (onQueueUpdated) onQueueUpdated();
    } catch (err) {
      alert('Failed to publish comment: ' + err.message);
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (commentId) => {
    const reason = prompt('Enter rejection reason (optional):', 'Not suitable for brand tone');
    if (reason === null) return;
    setProcessingId(commentId);
    try {
      await api.post(`/comments/${commentId}/reject`, { reason });
      await fetchQueue();
      if (onQueueUpdated) onQueueUpdated();
    } catch (err) {
      alert('Failed to reject comment: ' + err.message);
    } finally {
      setProcessingId(null);
    }
  };

  const handleRegenerate = async (commentId) => {
    setRegeneratingId(commentId);
    try {
      const res = await api.post(`/comments/${commentId}/regenerate`, {
        tone: selectedTone,
        target_language: selectedLang,
      });
      // Update local state with new draft
      setComments((prev) =>
        prev.map((c) => (c.id === commentId ? res.data : c))
      );
      if (editingId === commentId) {
        setEditedText(res.data.ai_draft_reply);
      }
    } catch (err) {
      alert('Regeneration failed: ' + err.message);
    } finally {
      setRegeneratingId(null);
    }
  };

  const startEditing = (comment) => {
    setEditingId(comment.id);
    setEditedText(comment.ai_draft_reply || '');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-xl font-bold text-slate-900">AI Comment Approval Queue</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
              {comments.length} Pending
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Review, edit, or regenerate bilingual responses before publishing to Facebook (ANNEX A §2.4).
          </p>
        </div>
        <button
          onClick={fetchQueue}
          disabled={loading}
          className="px-3.5 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Queue Items */}
      {loading && comments.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
          <p className="text-sm">Loading pending approval queue...</p>
        </div>
      ) : comments.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-3">
          <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
            <Check className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-slate-900">All Caught Up!</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            There are no comments waiting for approval. New comments from monitored Facebook Pages will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {comments.map((comment) => {
            const isEditing = editingId === comment.id;
            const isRegenerating = regeneratingId === comment.id;
            const isBusy = processingId === comment.id || isRegenerating;

            return (
              <div
                key={comment.id}
                className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden transition-all hover:border-slate-300"
              >
                {/* Comment Header */}
                <div className="p-4 bg-slate-50/70 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900 text-sm">{comment.sender_name}</span>
                    {comment.is_simulated && (
                      <span className="px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 text-[10px] font-bold">
                        Simulation only
                      </span>
                    )}
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-500 font-medium">{comment.page_name || 'Facebook Page'}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-400">
                      {new Date(comment.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    {/* Language Badge */}
                    <span className={`px-2 py-0.5 rounded-md font-semibold text-[11px] flex items-center gap-1 ${
                      comment.detected_language === 'ne'
                        ? 'bg-orange-50 text-orange-700 border border-orange-200'
                        : 'bg-blue-50 text-blue-700 border border-blue-200'
                    }`}>
                      <Languages className="w-3 h-3" />
                      {comment.detected_language === 'ne'
                        ? 'नेपाली (Nepali)'
                        : comment.detected_language === 'romanized_ne'
                          ? 'Romanized Nepali'
                          : 'English'}
                    </span>

                    {/* Sentiment Badge */}
                    <span className={`px-2 py-0.5 rounded-md font-semibold text-[11px] capitalize ${
                      comment.sentiment === 'positive'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : comment.sentiment === 'negative'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : comment.sentiment === 'question'
                        ? 'bg-purple-50 text-purple-700 border border-purple-200'
                        : 'bg-slate-100 text-slate-700'
                    }`}>
                      {comment.sentiment}
                    </span>

                    {/* Safety Alert Flag */}
                    {comment.error_message && (
                      <span className="px-2 py-0.5 rounded-md font-semibold text-[11px] bg-rose-100 text-rose-800 border border-rose-300 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 text-rose-600" />
                        Review required
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-5 space-y-4">
                  {/* Original Post Context */}
                  {comment.post_message && (
                    <div className="text-xs bg-slate-50 p-3 rounded-xl border border-slate-200/80 text-slate-600">
                      <span className="font-semibold text-slate-800 block mb-1">Post Reference:</span>
                      <p className="line-clamp-2 italic">"{comment.post_message}"</p>
                    </div>
                  )}

                  {/* Customer's Comment */}
                  <div className="flex items-start space-x-3">
                    <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-600 text-xs shrink-0">
                      {comment.sender_name.charAt(0)}
                    </div>
                    <div className="bg-slate-100/80 px-4 py-2.5 rounded-2xl rounded-tl-none text-sm text-slate-900 font-medium">
                      {comment.message}
                    </div>
                  </div>

                  {/* Warning notice if keyword flagged */}
                  {comment.error_message && (
                    <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                      <span>{comment.error_message}</span>
                    </div>
                  )}

                  {/* AI Response Draft Area */}
                  <div className="pl-11 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5 text-xs font-bold text-blue-700">
                        <Sparkles className="w-4 h-4 text-blue-600" />
                        <span>Suggested Reply</span>
                        {comment.ai_generation_source && (
                          <span className="font-medium text-slate-500">
                            {comment.ai_generation_source === 'local_fallback'
                              ? 'Local template — verify before publishing'
                              : 'Gemini'}
                          </span>
                        )}
                      </div>

                      {/* Quick Tone & Regenerate Controls */}
                      <div className="flex items-center space-x-2 text-xs">
                        <select
                          value={selectedTone}
                          onChange={(e) => setSelectedTone(e.target.value)}
                          className="px-2 py-1 bg-white border border-slate-200 rounded-lg text-slate-700 text-xs font-medium"
                        >
                          <option value="friendly">Friendly Tone</option>
                          <option value="professional">Professional</option>
                          <option value="support">Customer Support</option>
                          <option value="promotional">Promotional / Sales</option>
                        </select>
                        <select
                          value={selectedLang}
                          onChange={(e) => setSelectedLang(e.target.value)}
                          className="px-2 py-1 bg-white border border-slate-200 rounded-lg text-slate-700 text-xs font-medium"
                        >
                          <option value="ne">नेपाली</option>
                          <option value="en">English</option>
                        </select>
                        <button
                          onClick={() => handleRegenerate(comment.id)}
                          disabled={isBusy}
                          className="px-2.5 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold border border-blue-200 flex items-center gap-1 transition-colors"
                          title="Regenerate draft with selected tone and language"
                        >
                          <RefreshCw className={`w-3 h-3 ${isRegenerating ? 'animate-spin' : ''}`} />
                          <span>Regenerate</span>
                        </button>
                      </div>
                    </div>

                    {/* Draft Text or Edit Box */}
                    {isEditing ? (
                      <div className="space-y-2">
                        <textarea
                          rows={3}
                          value={editedText}
                          onChange={(e) => setEditedText(e.target.value)}
                          className="w-full p-3 text-sm bg-white border border-blue-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
                          placeholder="Type or modify reply..."
                        />
                        <div className="flex items-center justify-between text-xs text-slate-500">
                          <span>Nepali Devanagari or English supported</span>
                          <button
                            onClick={() => setEditingId(null)}
                            className="text-slate-500 hover:text-slate-800 underline"
                          >
                            Cancel Edit
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="p-3.5 rounded-xl bg-blue-50/70 border border-blue-200/70 text-sm text-slate-900 font-normal leading-relaxed relative group">
                        {comment.ai_draft_reply || 'No draft is available. Regenerate after checking AI configuration, or enter a reply manually.'}
                        <button
                          onClick={() => startEditing(comment)}
                          className="absolute top-2 right-2 p-1.5 bg-white/90 hover:bg-white text-slate-600 rounded-lg shadow-xs opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Edit this reply"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Action Bar */}
                  <div className="pl-11 pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
                    <label className="flex items-center space-x-2 text-xs text-slate-600 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={alsoLike}
                        onChange={(e) => setAlsoLike(e.target.checked)}
                        className="rounded-sm border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="flex items-center gap-1">
                        <ThumbsUp className="w-3 h-3 text-blue-600" />
                        Also like customer's comment (ANNEX A §2.5)
                      </span>
                    </label>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleReject(comment.id)}
                        disabled={isBusy}
                        className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 text-slate-600 text-xs font-semibold transition-colors flex items-center gap-1.5"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Reject</span>
                      </button>

                      {!isEditing && (
                        <button
                          onClick={() => startEditing(comment)}
                          disabled={isBusy}
                          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-colors flex items-center gap-1.5"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>Edit</span>
                        </button>
                      )}

                      {comment.is_simulated ? (
                        <span className="text-xs font-semibold text-amber-800">
                          Simulated comments cannot be published
                        </span>
                      ) : (
                        <button
                          onClick={() => handleApprove(comment.id)}
                          disabled={isBusy || !(isEditing ? editedText.trim() : comment.ai_draft_reply?.trim())}
                          className="px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all shadow-xs flex items-center gap-1.5"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>{isEditing ? 'Save & Publish' : 'Approve & Publish'}</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
