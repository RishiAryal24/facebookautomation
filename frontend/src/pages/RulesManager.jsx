import React, { useState, useEffect } from 'react';
import { Shield, Plus, Trash2, RefreshCw } from 'lucide-react';
import api from '../api';

export default function RulesManager() {
  const [keywords, setKeywords] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);

  // New Keyword Form
  const [newKeyword, setNewKeyword] = useState('');
  const [newCategory, setNewCategory] = useState('crisis');
  const [newAction, setNewAction] = useState('flag_for_review');

  // New Rule Form
  const [newRuleName, setNewRuleName] = useState('');
  const [newRuleKeyword, setNewRuleKeyword] = useState('');
  const [newRuleTemplate, setNewRuleTemplate] = useState('');
  const [newRuleLang, setNewRuleLang] = useState('auto');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [resKws, resRules] = await Promise.all([
        api.get('/rules/keywords'),
        api.get('/rules/')
      ]);
      setKeywords(resKws.data);
      setRules(resRules.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddKeyword = async (e) => {
    e.preventDefault();
    if (!newKeyword.trim()) return;
    try {
      await api.post('/rules/keywords', {
        keyword: newKeyword.trim(),
        category: newCategory,
        action: newAction
      });
      setNewKeyword('');
      await fetchData();
    } catch (err) {
      alert('Failed to add keyword: ' + err.message);
    }
  };

  const handleDeleteKeyword = async (id) => {
    try {
      await api.delete(`/rules/keywords/${id}`);
      await fetchData();
    } catch (err) {
      alert('Failed to delete keyword: ' + err.message);
    }
  };

  const handleAddRule = async (e) => {
    e.preventDefault();
    if (!newRuleName.trim()) return;
    try {
      await api.post('/rules/', {
        name: newRuleName,
        trigger_keyword: newRuleKeyword || null,
        response_template: newRuleTemplate || null,
        target_language: newRuleLang,
        is_active: true
      });
      setNewRuleName('');
      setNewRuleKeyword('');
      setNewRuleTemplate('');
      await fetchData();
    } catch (err) {
      alert('Failed to add rule: ' + err.message);
    }
  };

  const handleDeleteRule = async (id) => {
    try {
      await api.delete(`/rules/${id}`);
      await fetchData();
    } catch (err) {
      alert('Failed to delete rule: ' + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">
            Automation Rules &amp; Safety Policies
          </h1>
          <p className="mt-0.5 text-sm text-[#5b6475]">
            Restricted keywords, custom response templates and safety rules (ANNEX A §2.6).
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="min-h-[40px] px-4 rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] text-[#141a2e] text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </header>

      {/* Restricted Keywords Card */}
      <section className="bg-white rounded-2xl border border-[#e4e7ef] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-[#141a2e]">Restricted keywords</h2>
          <span className="bg-[#fde4e4] text-[#a31f1f] text-xs font-semibold px-2.5 py-0.5 rounded-full">
            {keywords.length} blocked
          </span>
        </div>
        <p className="text-xs text-[#5b6475]">
          Comments containing these terms are never auto-published. They go to the human approval queue.
        </p>

        {/* Add Keyword Form */}
        <form onSubmit={handleAddKeyword} className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          <input
            type="text"
            required
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            placeholder="Add a restricted word, e.g. scam, धोका..."
            className="flex-1 min-w-[220px] rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
          />
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            className="w-[180px] rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e]"
          >
            <option value="crisis">Crisis / Legal</option>
            <option value="complaint">Customer complaint</option>
            <option value="profanity">Profanity / abuse</option>
            <option value="competitor">Competitor brand</option>
          </select>
          <button
            type="submit"
            className="min-h-[42px] px-4 rounded-[10px] bg-[#1b2140] hover:bg-[#28315c] text-white font-semibold text-sm transition-colors cursor-pointer"
          >
            Add keyword
          </button>
        </form>

        {/* Keyword Chips */}
        <div className="flex flex-wrap gap-2 pt-2">
          {keywords.map((kw) => (
            <span
              key={kw.id}
              className="inline-flex items-center gap-2 bg-[#fde4e4] text-[#a31f1f] rounded-full pl-3 pr-1 py-1 text-xs font-semibold"
            >
              <span className={/[\u0900-\u097F]/.test(kw.keyword) ? 'font-devanagari' : ''}>
                {kw.keyword}
              </span>
              <span className="text-[10px] opacity-75 capitalize">
                {kw.category}
              </span>
              <button
                type="button"
                onClick={() => handleDeleteKeyword(kw.id)}
                aria-label={`Remove ${kw.keyword}`}
                className="w-5 h-5 rounded-full bg-white text-[#a31f1f] hover:bg-[#fde4e4] flex items-center justify-center font-bold text-xs transition-colors cursor-pointer border-0"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </section>

      {/* Custom Keyword & Template Rules */}
      <section className="bg-white rounded-2xl border border-[#e4e7ef] p-6 space-y-4">
        <h2 className="text-base font-bold text-[#141a2e]">Custom keyword &amp; template rules</h2>

        {/* Add Rule Form */}
        <form onSubmit={handleAddRule} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-[#5b6475] mb-1">Rule name</label>
              <input
                type="text"
                required
                value={newRuleName}
                onChange={(e) => setNewRuleName(e.target.value)}
                placeholder="e.g. Price inquiry instant reply"
                className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
              />
            </div>
            <div>
              <label className="block font-semibold text-[#5b6475] mb-1">Trigger keyword (optional)</label>
              <input
                type="text"
                value={newRuleKeyword}
                onChange={(e) => setNewRuleKeyword(e.target.value)}
                placeholder="e.g. price, kati, cost"
                className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
              />
            </div>
            <div>
              <label className="block font-semibold text-[#5b6475] mb-1">Language</label>
              <select
                value={newRuleLang}
                onChange={(e) => setNewRuleLang(e.target.value)}
                className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e]"
              >
                <option value="auto">Auto match</option>
                <option value="ne">Nepali (नेपाली)</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-[#5b6475] mb-1">Response template (optional override)</label>
            <input
              type="text"
              value={newRuleTemplate}
              onChange={(e) => setNewRuleTemplate(e.target.value)}
              placeholder="e.g. नमस्ते! कृपया मूल्य र अर्डरको लागि इनबक्स चेक गर्नुहोस्।"
              className="w-full rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] font-devanagari focus:outline-none focus:border-[#1b2140]"
            />
          </div>

          <button
            type="submit"
            className="min-h-[42px] px-4 rounded-[10px] bg-[#1b2140] hover:bg-[#28315c] text-white font-semibold text-sm transition-colors cursor-pointer"
          >
            Create automation rule
          </button>
        </form>

        {/* Existing Rules Table */}
        <div className="overflow-x-auto pt-2">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-[#eceef5] text-xs font-semibold text-[#5b6475]">
                <th className="pb-3 px-3">Rule</th>
                <th className="pb-3 px-3">Trigger</th>
                <th className="pb-3 px-3">Language</th>
                <th className="pb-3 px-3">Template</th>
                <th className="pb-3 px-3">Status</th>
                <th className="pb-3 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eceef5]">
              {rules.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-[#5b6475] text-xs">
                    No custom rules configured yet. The Gemini AI engine handles comments dynamically.
                  </td>
                </tr>
              ) : (
                rules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-[#f4f5f9]/50">
                    <td className="py-3 px-3 font-semibold text-[#141a2e]">{rule.name}</td>
                    <td className="py-3 px-3 font-mono text-xs text-[#5b6475]">{rule.trigger_keyword || 'All'}</td>
                    <td className="py-3 px-3 capitalize text-[#141a2e] text-xs">{rule.target_language}</td>
                    <td className="py-3 px-3 text-xs text-[#5b6475] max-w-xs truncate">{rule.response_template || 'Dynamic AI'}</td>
                    <td className="py-3 px-3">
                      <span className="bg-[#dff5ea] text-[#0b6b4a] text-xs font-semibold px-2 py-0.5 rounded-full">
                        Active
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="text-[#5b6475] hover:text-[#a31f1f] cursor-pointer"
                        title="Delete rule"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
