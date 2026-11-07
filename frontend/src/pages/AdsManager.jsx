import React, { useEffect, useState } from 'react';
import { AlertTriangle, Megaphone, RefreshCw, ShieldCheck } from 'lucide-react';
import api from '../api';

const formatCurrency = (value, currency) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency || 'NPR',
    minimumFractionDigits: 2,
  }).format(Number(value || 0));

export default function AdsManager() {
  const [account, setAccount] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [busyCampaignId, setBusyCampaignId] = useState(null);
  const [budgetDrafts, setBudgetDrafts] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([api.get('/ads/account'), api.get('/ads/campaigns')])
      .then(([accountResponse, campaignsResponse]) => {
        if (!active) return;
        setAccount(accountResponse.data);
        setCampaigns(campaignsResponse.data);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const syncCampaigns = async () => {
    setSyncing(true);
    setError('');
    try {
      const response = await api.post('/ads/sync');
      setCampaigns(response.data);
      setAccount((previous) => ({
        ...previous,
        connected: true,
        configured: true,
      }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSyncing(false);
    }
  };

  const updateBudget = async (campaign) => {
    const value = budgetDrafts[campaign.meta_campaign_id] ?? campaign.daily_budget;
    setBusyCampaignId(campaign.meta_campaign_id);
    setError('');
    try {
      const response = await api.patch(
        `/ads/campaigns/${campaign.meta_campaign_id}/budget`,
        { daily_budget: value },
      );
      setCampaigns((previous) =>
        previous.map((item) =>
          item.meta_campaign_id === campaign.meta_campaign_id ? response.data : item,
        ),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyCampaignId(null);
    }
  };

  const updateStatus = async (campaign) => {
    const status = campaign.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE';
    if (
      status === 'ACTIVE' &&
      !window.confirm(`Activate this campaign with a hard maximum budget of NPR 5.00/day?`)
    ) {
      return;
    }
    setBusyCampaignId(campaign.meta_campaign_id);
    setError('');
    try {
      const response = await api.patch(
        `/ads/campaigns/${campaign.meta_campaign_id}/status`,
        { status },
      );
      setCampaigns((previous) =>
        previous.map((item) =>
          item.meta_campaign_id === campaign.meta_campaign_id ? response.data : item,
        ),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyCampaignId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#141a2e]">Advertising &amp; Delivery</h1>
          <p className="mt-0.5 text-sm text-[#5b6475]">
            Authorized ad account campaign status, budgets and daily delivery snapshots.
          </p>
        </div>
        <button
          type="button"
          onClick={syncCampaigns}
          disabled={syncing || !account?.configured}
          className="min-h-[40px] rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] px-4 text-xs font-semibold text-[#141a2e] flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Refreshing…' : 'Refresh delivery'}
        </button>
      </header>

      {error && (
        <div role="alert" className="rounded-xl border border-[#e9b8b8] bg-[#fde4e4] p-3 text-sm text-[#a31f1f]">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 items-start">
        {/* Ad Account Card */}
        {account && (
          <section className="rounded-2xl border border-[#e4e7ef] bg-white p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-[#5b6475] uppercase tracking-wide">AD ACCOUNT</p>
                <h2 className="mt-1 text-xl font-bold text-[#141a2e]">
                  {account.name || account.account_id || 'Not connected'}
                </h2>
                {account.account_id && (
                  <p className="mt-1 font-mono text-xs text-[#5b6475]">{account.account_id}</p>
                )}
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                account.simulated
                  ? 'bg-[#ffe9c7] text-[#7a3f00]'
                  : account.connected
                  ? 'bg-[#dff5ea] text-[#0b6b4a]'
                  : 'bg-[#eceef5] text-[#3a4358]'
              }`}>
                {account.simulated ? 'Simulation only' : account.connected ? 'Connected' : 'Not configured'}
              </span>
            </div>
            <p className="text-xs text-[#5b6475] leading-relaxed">
              Set <code className="bg-[#f4f5f9] px-1.5 py-0.5 rounded text-[#141a2e] font-mono">META_AD_ACCOUNT_ID</code> and <code className="bg-[#f4f5f9] px-1.5 py-0.5 rounded text-[#141a2e] font-mono">META_AD_ACCESS_TOKEN</code> on the backend using an authorized account. Never enter access tokens on this screen.
            </p>
            <div className="flex items-center gap-2 rounded-xl bg-[#dff5ea] border border-[#0b6b4a]/20 p-3 text-xs font-semibold text-[#0b6b4a]">
              <ShieldCheck className="h-4 w-4 shrink-0" />
              Hard daily budget ceiling: {formatCurrency(account.max_daily_budget, account.currency)}
            </div>
          </section>
        )}

        {/* Campaign Cards */}
        {loading ? (
          <div className="rounded-2xl border border-[#e4e7ef] bg-white p-12 text-center text-sm text-[#5b6475]">
            Loading ad accounts and campaigns…
          </div>
        ) : campaigns.length === 0 ? (
          <div className="rounded-2xl border border-[#e4e7ef] bg-white p-10 text-center space-y-2">
            <AlertTriangle className="mx-auto h-8 w-8 text-[#5b6475]" />
            <p className="text-sm font-semibold text-[#141a2e]">No campaign snapshots</p>
            <p className="text-xs text-[#5b6475]">
              Connect an ad account and refresh delivery to load campaigns.
            </p>
          </div>
        ) : (
          campaigns.map((campaign) => (
            <article key={campaign.meta_campaign_id} className="rounded-2xl border border-[#e4e7ef] bg-white p-6 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-[#141a2e]">{campaign.name}</h3>
                  <p className="mt-0.5 font-mono text-xs text-[#5b6475]">
                    {campaign.objective || 'OUTCOME_AWARENESS'} · {campaign.meta_campaign_id}
                  </p>
                </div>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  campaign.status === 'ACTIVE'
                    ? 'bg-[#dff5ea] text-[#0b6b4a]'
                    : 'bg-[#eceef5] text-[#3a4358]'
                }`}>
                  {campaign.effective_status || campaign.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl bg-[#f4f5f9] p-3.5">
                  <div className="text-[#5b6475]">Today’s spend</div>
                  <div className="mt-1 font-bold text-lg text-[#141a2e]">
                    {formatCurrency(campaign.today_spend, campaign.currency)}
                  </div>
                </div>
                <div className="rounded-xl bg-[#f4f5f9] p-3.5">
                  <div className="text-[#5b6475]">Daily budget</div>
                  <div className="mt-1 font-bold text-lg text-[#141a2e]">
                    {campaign.daily_budget == null
                      ? 'Not set'
                      : formatCurrency(campaign.daily_budget, campaign.currency)}
                  </div>
                </div>
                <div className="rounded-xl bg-[#f4f5f9] p-3.5">
                  <div className="text-[#5b6475]">Impressions</div>
                  <div className="mt-1 font-bold text-lg text-[#141a2e]">{campaign.impressions}</div>
                </div>
                <div className="rounded-xl bg-[#f4f5f9] p-3.5">
                  <div className="text-[#5b6475]">Clicks</div>
                  <div className="mt-1 font-bold text-lg text-[#141a2e]">{campaign.clicks}</div>
                </div>
              </div>

              <div className="border-t border-[#eceef5] pt-4 space-y-2">
                <label className="block text-xs font-semibold text-[#5b6475]">
                  Daily budget (NPR, max 5)
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="number"
                    min="0.01"
                    max="5"
                    step="0.01"
                    value={budgetDrafts[campaign.meta_campaign_id] ?? campaign.daily_budget ?? ''}
                    onChange={(event) =>
                      setBudgetDrafts((previous) => ({
                        ...previous,
                        [campaign.meta_campaign_id]: event.target.value,
                      }))
                    }
                    className="flex-1 min-w-[120px] rounded-[10px] border border-[#d5d9e6] bg-white p-2.5 text-sm text-[#141a2e] focus:outline-none focus:border-[#1b2140]"
                  />
                  <button
                    type="button"
                    onClick={() => updateBudget(campaign)}
                    disabled={busyCampaignId === campaign.meta_campaign_id}
                    className="rounded-[10px] border border-[#d5d9e6] bg-white hover:bg-[#f4f5f9] px-3.5 py-2.5 text-xs font-semibold text-[#141a2e] disabled:opacity-50 cursor-pointer"
                  >
                    Save budget
                  </button>
                  <button
                    type="button"
                    onClick={() => updateStatus(campaign)}
                    disabled={busyCampaignId === campaign.meta_campaign_id}
                    className={`rounded-[10px] px-4 py-2.5 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer ${
                      campaign.status === 'ACTIVE'
                        ? 'border border-[#e9b8b8] bg-white text-[#a31f1f] hover:bg-[#fde4e4]'
                        : 'bg-[#0b6b4a] hover:bg-[#09573c] text-white'
                    }`}
                  >
                    {campaign.status === 'ACTIVE' ? 'Pause' : 'Activate'}
                  </button>
                </div>
              </div>

              <p className="text-[11px] text-[#5b6475]">
                Last checked: {campaign.last_synced_at ? new Date(campaign.last_synced_at).toLocaleString() : 'Not synced'}
              </p>
            </article>
          ))
        )}
      </div>
    </div>
  );
}
