import React, { useState } from 'react';
import { Send, ArrowRight } from 'lucide-react';
import api from '../api';

export default function Simulator({ onCommentSimulated, onNavigate }) {
  const [senderName, setSenderName] = useState('Anil Gurung');
  const [message, setMessage] = useState('सामानको मूल्य कति पर्छ होला? पोखरामा डेलिभरी छ?');
  const [submitting, setSubmitting] = useState(false);
  const [simResult, setSimResult] = useState(null);

  const presets = [
    {
      tag: 'NP · Nepali price & delivery',
      sender: 'Sita Sharma',
      text: 'यो सामानको मूल्य कति हो? बुटवलमा डेलिभरी हुन्छ कि नाइँ?',
      isDevanagari: true,
    },
    {
      tag: 'NP · Nepali positive feedback',
      sender: 'Ramesh Karki',
      text: 'सामान एकदमै राम्रो रहेछ, डेलिभरी पनि छिटो भयो। धन्यवाद!',
      isDevanagari: true,
    },
    {
      tag: 'EN · English price & warranty',
      sender: 'David Miller',
      text: 'PRICE please! How long is the battery life and warranty?',
      isDevanagari: false,
    },
    {
      tag: 'Safety check · restricted keyword',
      sender: 'Angry Customer',
      text: 'This is a scam and fake product, I want an immediate refund!',
      isDevanagari: false,
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
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">
            Live Simulation &amp; Testing Lab
          </h1>
          <p className="mt-0.5 text-sm text-[#5b6475]">
            Inject a Facebook comment in English or <span className="font-devanagari">नेपाली</span> to inspect AI reasoning, keyword filters and the approval pipeline.
          </p>
        </div>
        <span className="rounded-full bg-[#eceef5] text-[#3a4358] px-3.5 py-1 text-xs font-semibold">
          Nothing is posted to Facebook
        </span>
      </header>

      {/* Main 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left: Scenarios + Form */}
        <div className="space-y-4">
          <div className="text-xs font-bold text-[#5b6475] uppercase tracking-wide">
            Try a realistic scenario
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {presets.map((p, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleApplyPreset(p)}
                className="bg-white border border-[#e4e7ef] hover:border-[#1b2140] rounded-2xl p-4 text-left transition-colors cursor-pointer space-y-1 shadow-none"
              >
                <div className="text-xs font-bold text-[#2f3fb8]">{p.tag}</div>
                <p className={`text-xs text-[#5b6475] line-clamp-2 ${p.isDevanagari ? 'font-devanagari' : ''}`}>
                  “{p.text}”
                </p>
              </button>
            ))}
          </div>

          <form onSubmit={handleSimulate} className="bg-white rounded-2xl border border-[#e4e7ef] p-6 space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#5b6475] mb-1.5" htmlFor="sim-name">
                Simulated customer name
              </label>
              <input
                id="sim-name"
                type="text"
                required
                value={senderName}
                onChange={(e) => setSenderName(e.target.value)}
                className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#5b6475] mb-1.5" htmlFor="sim-comment">
                Facebook comment (Nepali or English)
              </label>
              <textarea
                id="sim-comment"
                rows={4}
                required
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-3 text-sm text-[#141a2e] font-devanagari focus:outline-none focus:border-[#1b2140]"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full min-h-[46px] rounded-xl bg-[#1b2140] hover:bg-[#28315c] text-white font-bold text-sm transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              <span>{submitting ? 'Running Gemini AI pipeline…' : 'Inject simulated comment'}</span>
            </button>
          </form>
        </div>

        {/* Right: Pipeline Result Card */}
        <div className="bg-white rounded-2xl border border-[#e4e7ef] p-6 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#eceef5]">
            <h2 className="text-base font-bold text-[#141a2e]">Pipeline result</h2>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
              simResult ? 'bg-[#dff5ea] text-[#0b6b4a]' : 'bg-[#eceef5] text-[#3a4358]'
            }`}>
              {simResult ? 'Live result' : 'Example'}
            </span>
          </div>

          <div className="divide-y divide-[#eceef5]">
            {/* Step 1 */}
            <div className="flex items-center gap-3 py-3 text-sm">
              <span className="w-6 h-6 rounded-full bg-[#0b6b4a] text-white flex items-center justify-center text-xs font-bold shrink-0">
                1
              </span>
              <span className="text-[#5b6475] flex-1">Language detected</span>
              <strong className="text-[#141a2e] capitalize">
                {simResult
                  ? simResult.detected_language === 'ne'
                    ? 'Nepali (नेपाली)'
                    : simResult.detected_language === 'romanized_ne'
                    ? 'Romanized Nepali'
                    : 'English'
                  : 'Nepali'}
              </strong>
            </div>

            {/* Step 2 */}
            <div className="flex items-center gap-3 py-3 text-sm">
              <span className="w-6 h-6 rounded-full bg-[#0b6b4a] text-white flex items-center justify-center text-xs font-bold shrink-0">
                2
              </span>
              <span className="text-[#5b6475] flex-1">Sentiment</span>
              <span className="bg-[#dff5ea] text-[#0b6b4a] text-xs font-semibold px-2.5 py-0.5 rounded-full capitalize">
                {simResult ? simResult.sentiment : 'Price inquiry'}
              </span>
            </div>

            {/* Step 3 */}
            <div className="flex items-center gap-3 py-3 text-sm">
              <span className="w-6 h-6 rounded-full bg-[#0b6b4a] text-white flex items-center justify-center text-xs font-bold shrink-0">
                3
              </span>
              <span className="text-[#5b6475] flex-1">Restricted keyword check</span>
              <span
                className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${
                  simResult?.error_message
                    ? 'bg-[#fde4e4] text-[#a31f1f]'
                    : 'bg-[#dff5ea] text-[#0b6b4a]'
                }`}
              >
                {simResult ? (simResult.error_message ? 'Flagged' : 'Clear') : 'Clear'}
              </span>
            </div>

            {/* Step 4 */}
            <div className="flex items-center gap-3 py-3 text-sm">
              <span className="w-6 h-6 rounded-full bg-[#0b6b4a] text-white flex items-center justify-center text-xs font-bold shrink-0">
                4
              </span>
              <span className="text-[#5b6475] flex-1">Decision</span>
              <strong className="text-[#141a2e]">
                {simResult
                  ? simResult.status === 'published'
                    ? 'Auto-publish directly'
                    : 'Send to approval queue'
                  : 'Send to approval queue'}
              </strong>
            </div>
          </div>

          {/* AI Reply Quote */}
          <div className="rounded-xl bg-[#f4f5f9] p-4 text-sm text-[#141a2e] leading-relaxed font-devanagari space-y-1">
            <div className="text-xs font-semibold text-[#5b6475] mb-1">AI draft reply</div>
            <div>
              {simResult
                ? simResult.ai_draft_reply || 'No draft generated.'
                : 'नमस्ते अनिल जी! मूल्य र पोखरा डेलिभरीको जानकारीको लागि कृपया इनबक्स चेक गर्नुहोस्।'}
            </div>
          </div>

          {simResult && (
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => onNavigate('queue')}
                className="px-4 py-2 bg-[#1b2140] hover:bg-[#28315c] text-white text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <span>View in Approval Queue</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
