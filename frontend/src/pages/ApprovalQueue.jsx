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
  ThumbsUp,
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
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">Approval Queue</h1>
            {comments.length > 0 && (
              <span className="bg-[#ffe3b8] text-[#7a3f00] text-xs font-bold px-2.5 py-0.5 rounded-full">
                {comments.length}
              </span>
            )}
          </div>
          <p className="text-sm text-[#5b6475] mt-0.5">
            {comments.length === 0
              ? 'All caught up. Nothing is waiting in the queue.'
              : `${comments.length} AI replies waiting. Nothing is posted until you approve it.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchQueue}
            disabled={loading}
            className="min-h-[40px] rounded-[10px] border border-[#d5d9e6] bg-white px-4 text-xs font-semibold text-[#141a2e] hover:bg-[#f4f5f9] flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      {/* Queue Items */}
      {loading && comments.length === 0 ? (
        <div className="p-16 text-center text-[#5b6475] bg-white rounded-2xl border border-[#e4e7ef]">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-[#1b2140]" />
          <p className="text-sm">Loading pending approval queue...</p>
        </div>
      ) : comments.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-2xl border border-[#e4e7ef] space-y-3">
          <div className="w-12 h-12 bg-[#dff5ea] text-[#0b6b4a] rounded-full flex items-center justify-center mx-auto">
            <Check className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-[#141a2e] text-base">All Caught Up!</h3>
          <p className="text-xs text-[#5b6475] max-w-sm mx-auto">
            There are no comments waiting for approval. New comments arrive through configured Meta webhooks or manual post sync.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
          {comments.map((comment) => {
            const isEditing = editingId === comment.id;
            const isRegenerating = regeneratingId === comment.id;
            const isBusy = processingId === comment.id || isRegenerating;

            return (
              <div
                key={comment.id}
                className="bg-white rounded-2xl border border-[#e4e7ef] p-5 md:p-6 space-y-3.5 transition-shadow hover:shadow-xs"
              >
                {/* Comment Meta Header */}
                <div className="flex flex-wrap items-center gap-2">
                  <strong className="text-sm font-bold text-[#141a2e]">{comment.sender_name}</strong>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                      comment.sentiment === 'positive'
                        ? 'bg-[#dff5ea] text-[#0b6b4a]'
                        : comment.sentiment === 'negative'
                        ? 'bg-[#fde4e4] text-[#a31f1f]'
                        : 'bg-[#ffe9c7] text-[#7a3f00]'
                    }`}
                  >
                    {comment.sentiment || 'Neutral'}
                  </span>
                  <span className="rounded-full bg-[#eceef5] text-[#3a4358] px-2.5 py-0.5 text-xs font-semibold">
                    {comment.detected_language === 'ne' ? 'नेपाली' : 'English'}
                  </span>
                  {comment.is_simulated && (
                    <span className="rounded-full bg-[#ffe9c7] text-[#7a3f00] px-2 py-0.5 text-[11px] font-bold">
                      Simulated
                    </span>
                  )}
                  <span className="ml-auto text-xs text-[#5b6475]">
                    {new Date(comment.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>

                {/* Original Post Context if available */}
                {comment.post_message && (
                  <div className="text-xs bg-[#f4f5f9] border border-[#e4e7ef] rounded-xl p-2.5 text-[#5b6475]">
                    <span className="font-semibold text-[#141a2e] block mb-0.5">Post context:</span>
                    <p className="line-clamp-2 italic text-[11px]">"{comment.post_message}"</p>
                  </div>
                )}

                {/* Customer Comment Text */}
                <div className="text-sm text-[#141a2e] leading-relaxed">
                  {comment.message}
                </div>

                {/* Safety Warning if flagged */}
                {comment.error_message && (
                  <div className="p-3 rounded-xl bg-[#fff8eb] border border-[#ffe3b8] text-[#7a3f00] text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-[#c97700]" />
                    <span>{comment.error_message}</span>
                  </div>
                )}

                {/* AI Draft Box */}
                <div className="rounded-xl bg-[#f4f5f9] p-3.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-[#5b6475] flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[#1b2140]" />
                      <span>AI draft reply</span>
                    </div>

                    {/* Tone & Lang selector */}
                    <div className="flex items-center gap-1.5 text-xs">
                      <select
                        value={selectedTone}
                        onChange={(e) => setSelectedTone(e.target.value)}
                        className="rounded-lg border border-[#d5d9e6] bg-white px-2 py-1 text-[11px] text-[#141a2e]"
                      >
                        <option value="friendly">Friendly</option>
                        <option value="formal">Formal</option>
                        <option value="support">Support</option>
                      </select>
                      <select
                        value={selectedLang}
                        onChange={(e) => setSelectedLang(e.target.value)}
                        className="rounded-lg border border-[#d5d9e6] bg-white px-2 py-1 text-[11px] text-[#141a2e]"
                      >
                        <option value="ne">नेपाली</option>
                        <option value="en">English</option>
                      </select>
                      <button
                        onClick={() => handleRegenerate(comment.id)}
                        disabled={isBusy}
                        className="rounded-lg border border-[#d5d9e6] bg-white hover:bg-[#eceef5] px-2 py-1 text-[11px] font-semibold text-[#141a2e] disabled:opacity-50 cursor-pointer"
                        title="Regenerate draft"
                      >
                        <RefreshCw className={`w-3 h-3 ${isRegenerating ? 'animate-spin' : ''}`} />
                      </button>
                    </div>
                  </div>

                  {isEditing ? (
                    <div className="space-y-2 pt-1">
                      <textarea
                        rows={3}
                        value={editedText}
                        onChange={(e) => setEditedText(e.target.value)}
                        className="w-full rounded-[10px] border border-[#d5d9e6] p-2.5 text-sm bg-white text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
                        placeholder="Modify draft reply..."
                      />
                      <div className="flex justify-end">
                        <button
                          onClick={() => setEditingId(null)}
                          className="text-xs text-[#5b6475] hover:text-[#141a2e] underline cursor-pointer"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-[#141a2e] leading-relaxed whitespace-pre-line">
                      {comment.ai_draft_reply || 'No draft generated yet. Regenerate or enter a reply manually.'}
                    </div>
                  )}
                </div>

                {/* Action Bar */}
                <div className="pt-2 border-t border-[#eceef5] flex flex-wrap items-center justify-between gap-2">
                  {comment.platform !== 'instagram' && (
                    <label className="flex items-center gap-1.5 text-xs text-[#5b6475] cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={alsoLike}
                        onChange={(e) => setAlsoLike(e.target.checked)}
                      />
                      <span className="flex items-center gap-1 text-[#141a2e]">
                        <ThumbsUp className="w-3 h-3 text-[#1b2140]" />
                        Also like comment
                      </span>
                    </label>
                  )}

                  <div className="flex items-center gap-2 ml-auto">
                    {comment.is_simulated ? (
                      <span className="text-xs font-semibold text-[#7a3f00]">
                        Simulated comments cannot be published
                      </span>
                    ) : (
                      <button
                        onClick={() => handleApprove(comment.id)}
                        disabled={isBusy || !(isEditing ? editedText.trim() : comment.ai_draft_reply?.trim())}
                        className="min-h-[38px] rounded-[10px] bg-[#0b6b4a] hover:bg-[#09573c] px-4 py-1.5 text-xs font-semibold text-white transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <Send className="w-3 h-3" />
                        <span>{isEditing ? 'Save & post' : 'Approve & post'}</span>
                      </button>
                    )}

                    {!isEditing && (
                      <button
                        onClick={() => startEditing(comment)}
                        disabled={isBusy}
                        className="min-h-[38px] rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] px-3 py-1.5 text-xs font-semibold text-[#141a2e] transition-colors cursor-pointer flex items-center gap-1.5"
                      >
                        <Edit3 className="w-3 h-3 text-[#5b6475]" />
                        <span>Edit</span>
                      </button>
                    )}

                    <button
                      onClick={() => handleReject(comment.id)}
                      disabled={isBusy}
                      className="min-h-[38px] rounded-[10px] border border-[#e9b8b8] bg-white hover:bg-[#fde4e4] px-3 py-1.5 text-xs font-semibold text-[#a31f1f] transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <X className="w-3 h-3" />
                      <span>Reject</span>
                    </button>
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
