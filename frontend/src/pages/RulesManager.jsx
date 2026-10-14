import React, { useState, useEffect } from 'react';
import { Shield, Plus, Trash2, AlertTriangle, Sliders, RefreshCw, Check } from 'lucide-react';
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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Automation Rules & Safety Policies</h2>
          <p className="text-xs text-slate-500 mt-1">
            Configure restricted keywords, custom response templates, and safety rules (ANNEX A §2.6).
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-3.5 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Restricted Keywords Section */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
        <div className="flex items-center space-x-2 text-slate-900 font-bold">
          <Shield className="w-5 h-5 text-rose-600" />
          <h3 className="text-base">Restricted Keywords (Blacklist & Safety Guardrails)</h3>
        </div>
        <p className="text-xs text-slate-500">
          When an incoming Facebook comment contains any of these terms, the system refuses to auto-publish and routes it to the human approval queue.
        </p>

        {/* Add Keyword Form */}
        <form onSubmit={handleAddKeyword} className="flex flex-wrap items-center gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
          <input
            type="text"
            required
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            placeholder="Add restricted word (e.g. scam, fraud, धोका)..."
            className="flex-1 min-w-[200px] p-2 bg-white rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            className="p-2 bg-white rounded-lg border border-slate-300 text-xs"
          >
            <option value="crisis">Crisis / Legal</option>
            <option value="complaint">Customer Complaint</option>
            <option value="profanity">Profanity / Abuse</option>
            <option value="competitor">Competitor Brand</option>
          </select>
          <button
            type="submit"
            className="px-4 py-2 bg-slate-900 hover:bg-black text-white font-bold rounded-lg transition-colors flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Keyword</span>
          </button>
        </form>

        {/* Keyword Chips */}
        <div className="flex flex-wrap gap-2 pt-2">
          {keywords.map((kw) => (
            <div
              key={kw.id}
              className="flex items-center space-x-2 px-3 py-1.5 bg-rose-50 border border-rose-200 rounded-xl text-xs"
            >
              <AlertTriangle className="w-3 h-3 text-rose-500" />
              <span className="font-semibold text-rose-900">{kw.keyword}</span>
              <span className="text-[10px] text-rose-600 uppercase font-mono tracking-tight bg-rose-100/60 px-1.5 py-0.5 rounded">
                {kw.category}
              </span>
              <button
                onClick={() => handleDeleteKeyword(kw.id)}
                className="text-rose-400 hover:text-rose-700 transition-colors"
                title="Remove keyword"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Custom Automation Rules Section */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
        <div className="flex items-center space-x-2 text-slate-900 font-bold">
          <Sliders className="w-5 h-5 text-blue-600" />
          <h3 className="text-base">Custom Keyword & Template Rules</h3>
        </div>

        {/* Add Rule Form */}
        <form onSubmit={handleAddRule} className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Rule Name</label>
              <input
                type="text"
                required
                value={newRuleName}
                onChange={(e) => setNewRuleName(e.target.value)}
                placeholder="e.g. Price Inquiry Instant Reply"
                className="w-full p-2 bg-white rounded-lg border border-slate-300"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Trigger Keyword (Optional)</label>
              <input
                type="text"
                value={newRuleKeyword}
                onChange={(e) => setNewRuleKeyword(e.target.value)}
                placeholder="e.g. price, kati, cost"
                className="w-full p-2 bg-white rounded-lg border border-slate-300"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Language</label>
              <select
                value={newRuleLang}
                onChange={(e) => setNewRuleLang(e.target.value)}
                className="w-full p-2 bg-white rounded-lg border border-slate-300"
              >
                <option value="auto">Auto Match</option>
                <option value="ne">Nepali (नेपाली)</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Response Template (Optional Override)</label>
            <input
              type="text"
              value={newRuleTemplate}
              onChange={(e) => setNewRuleTemplate(e.target.value)}
              placeholder="e.g. नमस्ते! कृपया मूल्य र अर्डरको लागि इनबक्स चेक गर्नुहोस्। 🙏"
              className="w-full p-2 bg-white rounded-lg border border-slate-300"
            />
          </div>

          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg transition-colors flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Automation Rule</span>
          </button>
        </form>

        {/* Existing Rules Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="p-3">Rule Name</th>
                <th className="p-3">Trigger</th>
                <th className="p-3">Language</th>
                <th className="p-3">Template / Action</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rules.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-slate-400">
                    No custom rules configured yet. The Gemini AI engine will handle comments dynamically.
                  </td>
                </tr>
              ) : (
                rules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-slate-50/70">
                    <td className="p-3 font-bold text-slate-900">{rule.name}</td>
                    <td className="p-3 text-slate-600 font-mono">{rule.trigger_keyword || 'All Comments'}</td>
                    <td className="p-3 capitalize">{rule.target_language}</td>
                    <td className="p-3 text-slate-600 truncate max-w-xs">{rule.response_template || 'AI Dynamic Generation'}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Active
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
