import React, { useEffect, useState } from 'react';
import { AlertTriangle, Megaphone, RefreshCw, ShieldCheck } from 'lucide-react';
import api from '../api';

const formatCurrency = (value, currency) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
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
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Megaphone className="h-6 w-6 text-indigo-600" />
            <h2 className="text-xl font-bold text-slate-900">Advertising & Delivery</h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Authorized Ad Account campaign status, budgets, and daily delivery snapshots.
          </p>
        </div>
        <button
          type="button"
          onClick={syncCampaigns}
          disabled={syncing || !account?.configured}
          className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Refreshing…' : 'Refresh delivery'}
        </button>
      </header>

      {error && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {account && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Ad Account</p>
              <h3 className="mt-1 font-bold text-slate-900">
                {account.name || account.account_id || 'Not connected'}
              </h3>
              {account.account_id && (
                <p className="mt-1 font-mono text-xs text-slate-500">{account.account_id}</p>
              )}
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${
              account.simulated
                ? 'bg-amber-100 text-amber-800'
                : account.connected
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-slate-100 text-slate-700'
            }`}>
              {account.simulated ? 'Simulation only' : account.connected ? 'Connected' : 'Not configured'}
            </span>
          </div>
          <p className="mt-3 text-xs text-slate-600">{account.message}</p>
          <div className="mt-4 flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-900">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Hard daily budget ceiling: {formatCurrency(account.max_daily_budget, account.currency)}
          </div>
        </section>
      )}

      {!loading && account && !account.configured && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Set <code>META_AD_ACCOUNT_ID</code> and <code>META_AD_ACCESS_TOKEN</code> on the backend
          using an authorized account. Never enter access tokens in this screen.
        </div>
      )}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          Loading Ad Account…
        </div>
      ) : campaigns.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-slate-400" />
          <p className="mt-3 text-sm font-semibold text-slate-700">No campaign snapshots</p>
          <p className="mt-1 text-xs text-slate-500">
            Connect an Ad Account and refresh delivery to load campaigns.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {campaigns.map((campaign) => (
            <article key={campaign.meta_campaign_id} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-bold text-slate-900">{campaign.name}</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    {campaign.objective || 'Campaign'} · {campaign.meta_campaign_id}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                  {campaign.effective_status || campaign.status}
                </span>
              </div>

              <dl className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl bg-slate-50 p-3">
                  <dt className="text-slate-500">Today’s spend</dt>
                  <dd className="mt-1 font-bold text-slate-900">
                    {formatCurrency(campaign.today_spend, campaign.currency)}
                  </dd>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <dt className="text-slate-500">Daily budget</dt>
                  <dd className="mt-1 font-bold text-slate-900">
                    {campaign.daily_budget == null
                      ? 'Not set'
                      : formatCurrency(campaign.daily_budget, campaign.currency)}
                  </dd>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <dt className="text-slate-500">Impressions</dt>
                  <dd className="mt-1 font-bold text-slate-900">{campaign.impressions}</dd>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <dt className="text-slate-500">Clicks</dt>
                  <dd className="mt-1 font-bold text-slate-900">{campaign.clicks}</dd>
                </div>
              </dl>

              <div className="flex flex-wrap items-end gap-2 border-t border-slate-100 pt-4">
                <label className="min-w-36 flex-1 text-xs font-semibold text-slate-600">
                  Daily budget (NPR, max 5)
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
                    className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => updateBudget(campaign)}
                  disabled={busyCampaignId === campaign.meta_campaign_id}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-50"
                >
                  Save budget
                </button>
                <button
                  type="button"
                  onClick={() => updateStatus(campaign)}
                  disabled={busyCampaignId === campaign.meta_campaign_id}
                  className={`rounded-lg px-3 py-2 text-xs font-bold text-white disabled:opacity-50 ${
                    campaign.status === 'ACTIVE' ? 'bg-rose-600' : 'bg-emerald-600'
                  }`}
                >
                  {campaign.status === 'ACTIVE' ? 'Pause' : 'Activate'}
                </button>
              </div>
              <p className="text-[11px] text-slate-400">
                Last checked: {campaign.last_synced_at ? new Date(campaign.last_synced_at).toLocaleString() : 'Not synced'}
              </p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
