import React, { useState } from 'react';
import { FlaskConical, Send, Sparkles, CheckCircle2, AlertTriangle, ArrowRight, CornerDownRight } from 'lucide-react';
import api from '../api';

export default function Simulator({ onCommentSimulated, onNavigate }) {
  const [senderName, setSenderName] = useState('Anil Gurung');
  const [message, setMessage] = useState('सामानको मूल्य कति पर्छ होला? पोखरामा डेलिभरी छ?');
  const [submitting, setSubmitting] = useState(false);
  const [simResult, setSimResult] = useState(null);

  const presets = [
    {
      label: '🇳🇵 Nepali Price & Delivery',
      sender: 'Sita Sharma',
      text: 'यो सामानको मूल्य कति हो? बुटवलमा डेलिभरी हुन्छ कि नाइँ?',
    },
    {
      label: '🇳🇵 Nepali Positive Feedback',
      sender: 'Ramesh Karki',
      text: 'सामान एकदमै राम्रो रहेछ, डेलिभरी पनि छिटो भयो। धन्यवाद!',
    },
    {
      label: '🇬🇧 English Price & Warranty',
      sender: 'David Miller',
      text: 'PRICE please! How long is the battery life and warranty?',
    },
    {
      label: '⚠️ Restricted Keyword (Safety Check)',
      sender: 'Angry Customer',
      text: 'This is a scam and fake product, I want an immediate refund!',
    },
  ];

  const handleApplyPreset = (preset) => {
    setSenderName(preset.sender);
    setMessage(preset.text);
    setSimResult(null);
  };

  const handleSimulate = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    setSubmitting(true);
    setSimResult(null);
    try {
      const res = await api.post('/comments/simulate', {
        page_id: 1, // Default page
        sender_name: senderName,
        message: message.trim(),
      });
      setSimResult(res.data);
      if (onCommentSimulated) onCommentSimulated();
    } catch (err) {
      alert('Simulation failed: ' + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <div className="flex items-center space-x-2">
          <FlaskConical className="w-6 h-6 text-indigo-600" />
          <h2 className="text-xl font-bold text-slate-900">Live Simulation & Testing Lab</h2>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Simulate incoming Facebook customer comments in English or Nepali to inspect bilingual AI reasoning, keyword filters, and the approval pipeline.
        </p>
      </div>

      {/* Quick Presets */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-slate-600 block">Try a Realistic Scenario:</span>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {presets.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleApplyPreset(p)}
              className="p-3 bg-white hover:bg-indigo-50/60 border border-slate-200 hover:border-indigo-300 rounded-xl text-left text-xs transition-all shadow-xs group"
            >
              <div className="font-bold text-slate-800 group-hover:text-indigo-600 flex items-center justify-between">
                <span>{p.label}</span>
                <CornerDownRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-slate-500 mt-1 truncate">"{p.text}"</p>
            </button>
          ))}
        </div>
      </div>

      {/* Interactive Form */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
        <form onSubmit={handleSimulate} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Simulated Customer Name</label>
            <input
              type="text"
              required
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              className="w-full p-2.5 bg-slate-50 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Facebook Comment Text (Nepali or English)</label>
            <textarea
              rows={3}
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Type any comment in Nepali or English..."
              className="w-full p-3 bg-slate-50 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-sm flex items-center justify-center gap-2 text-sm"
          >
            <Send className="w-4 h-4" />
            <span>{submitting ? 'Running Gemini AI Pipeline...' : 'Inject Simulated Comment'}</span>
          </button>
        </form>
      </div>

      {/* Live Pipeline Execution Result */}
      {simResult && (
        <div className="bg-white rounded-2xl border border-indigo-200 p-6 shadow-md space-y-5 animate-in fade-in duration-300">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center space-x-2 text-indigo-700 font-bold">
              <Sparkles className="w-5 h-5 text-indigo-600" />
              <span>Pipeline Execution Complete</span>
            </div>
            <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
              simResult.status === 'published'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200'
            }`}>
              {simResult.status === 'published' ? 'Directly Auto-Published' : 'Sent to Approval Queue'}
            </span>
          </div>

          {/* Breakdown Steps */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Language Detected</span>
              <span className="font-bold text-slate-900 text-sm capitalize">
                {simResult.detected_language === 'ne'
                  ? 'नेपाली (Nepali)'
                  : simResult.detected_language === 'romanized_ne'
                    ? 'Romanized Nepali'
                    : 'English'}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Sentiment / Intent</span>
              <span className="font-bold text-slate-900 text-sm capitalize">{simResult.sentiment}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Policy Safety Status</span>
              <span className={`font-bold text-sm ${simResult.error_message ? 'text-rose-600' : 'text-emerald-600'}`}>
                {simResult.error_message ? 'Flagged by Filter' : 'Passed Safety Check'}
              </span>
            </div>
          </div>

          {/* AI Response Output */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-slate-700">Suggested Reply:</span>
            <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-xl text-slate-900 text-sm leading-relaxed font-medium">
              {simResult.ai_draft_reply || 'No draft generated. Check AI configuration or review the comment manually.'}
            </div>
            {simResult.ai_generation_source === 'local_fallback' && (
              <p className="text-xs font-semibold text-amber-700">
                Local template fallback — verify before publishing.
              </p>
            )}
          </div>

          {/* Navigation to Queue */}
          <div className="pt-2 flex justify-end">
            <button
              onClick={() => onNavigate('queue')}
              className="px-4 py-2 bg-slate-900 hover:bg-black text-white text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5"
            >
              <span>View in Approval Queue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
