import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  Filter,
  Radio,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { api } from '../api/client';
import type { RingListItem, HeroRing } from '../api/client';
import { RiskBadge, ScoreBar } from '../components/RiskBadge';
import { useLiveData } from '../context/LiveDataContext';

type Band = 'All' | 'Critical' | 'High' | 'Medium' | 'Low';
type SortKey = 'risk_score' | 'account_count' | 'evidence_count';

const EVIDENCE_LABELS: Record<string, string> = {
  shared_device:            'Shared Device',
  shared_ip:                'Shared IP',
  refund_ratio:             'Refund Elevation',
  circular_flow:            'Circular Flow',
  transaction_concentration:'Txn Concentration',
  temporal_sync:            'Temporal Sync',
  high_velocity:            'High Velocity',
};

export function RiskOverview() {
  const navigate = useNavigate();
  const { isConnected, status, latestUpdate } = useLiveData();
  const [rings, setRings]       = useState<RingListItem[]>([]);
  const [heroRing, setHeroRing] = useState<HeroRing | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [band, setBand]         = useState<Band>('All');
  const [sortKey, setSortKey]   = useState<SortKey>('risk_score');
  const [sortAsc, setSortAsc]   = useState(false);

  useEffect(() => {
    Promise.all([
      api.listRings(),
      api.getHeroRing().catch(() => null),
    ])
      .then(([ringsData, heroData]) => {
        setRings(ringsData);
        setHeroRing(heroData);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let r = band === 'All' ? rings : rings.filter((x) => x.risk_band === band);
    r = [...r].sort((a, b) => {
      const delta = (a[sortKey] as number) - (b[sortKey] as number);
      return sortAsc ? delta : -delta;
    });
    return r;
  }, [rings, band, sortKey, sortAsc]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    rings.forEach((r) => c[r.risk_band]++);
    return c;
  }, [rings]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span style={{ opacity: 0.3 }}><ChevronDown size={12} /></span>;
    return sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />;
  }

  if (loading) {
    return (
      <div className="page loading-state">
        <div className="spinner" />
        <span>Loading ring detection results...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page empty-state">
        <AlertTriangle size={32} color="var(--risk-high)" />
        <span style={{ color: 'var(--risk-high)' }}>API Error: {error}</span>
        <span className="text-muted text-sm">Is the backend running on port 8000?</span>
      </div>
    );
  }

  return (
    <div className="page space-y-6">
      {/* Top Banner: Real-Time Stream Status & Quick Launch */}
      <div className="card p-4 bg-gradient-to-r from-slate-900 via-cyan-950/20 to-slate-900 border-cyan-900/40 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded bg-cyan-950/80 border border-cyan-700/60 flex items-center justify-center text-cyan-400">
            <Radio className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-2">
              <span>Real-Time Stream Active</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                {isConnected ? 'WebSocket Connected' : 'Reconnecting'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {latestUpdate
                ? `Latest event ${latestUpdate.event_id}: ${latestUpdate.buyer_id} to ${latestUpdate.merchant_id}, risk ${latestUpdate.risk_score.toFixed(1)}`
                : 'No live event received in this browser session.'}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto">
          <button
            onClick={() => navigate('/live')}
            className="btn-primary text-xs flex items-center gap-1.5"
          >
            <Radio className="h-3.5 w-3.5" />
            Open Live Stream
          </button>
          <button
            onClick={() => navigate('/simulator')}
            className="btn-secondary text-xs flex items-center gap-1.5"
          >
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
            Manual Simulator
          </button>
        </div>
      </div>

      <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <div className="metric-card"><div className="metric-label">Transactions processed</div><div className="metric-value">{status?.transactions ?? '—'}</div><div className="metric-sub">Live engine total</div></div>
        <div className="metric-card"><div className="metric-label">Monitored accounts</div><div className="metric-value">{status?.accounts ?? '—'}</div><div className="metric-sub">In-memory graph</div></div>
        <div className="metric-card"><div className="metric-label">Flagged rings</div><div className="metric-value">{status?.flagged_rings ?? '—'}</div><div className="metric-sub">Current graph clusters</div></div>
        <div className="metric-card"><div className="metric-label">Last risk delta</div><div className="metric-value" style={{ color: latestUpdate?.risk_delta && latestUpdate.risk_delta > 0 ? 'var(--risk-high)' : undefined }}>{latestUpdate ? `${latestUpdate.risk_delta > 0 ? '+' : ''}${latestUpdate.risk_delta.toFixed(1)}` : '—'}</div><div className="metric-sub">Actual most recent update</div></div>
      </div>

      {/* Hero Ring Spotlight Card (if present) */}
      {heroRing && (
        <div
          onClick={() => navigate(`/ring/${heroRing.ring_id}`)}
          className="card p-4 border-cyan-600/60 bg-gradient-to-r from-cyan-950/40 via-slate-900 to-indigo-950/30 cursor-pointer hover:border-cyan-400 transition"
        >
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700">
                  DEMO HERO CASE
                </span>
                <span className="font-bold text-sm text-slate-100 font-mono">{heroRing.ring_id}</span>
                <RiskBadge score={heroRing.risk_score} band={heroRing.risk_band} />
              </div>
              <p className="text-xs text-slate-300">
                Full-spectrum coordinated fraud ring ({heroRing.account_count} accounts): Shared Device + Shared IP + Circular Money Flow + Creation Synchronization.
              </p>
            </div>
            <div className="flex items-center gap-1 text-xs text-cyan-400 font-medium">
              <span>Investigate Hero Ring</span>
              <ArrowRight className="h-4 w-4" />
            </div>
          </div>
        </div>
      )}

      {/* Band summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {(['Critical', 'High', 'Medium', 'Low'] as const).map((b) => (
          <div
            key={b}
            className={`card p-4 cursor-pointer transition ${
              band === b ? 'border-cyan-500 bg-slate-800/80' : 'hover:border-slate-700'
            }`}
            onClick={() => setBand(b === band ? 'All' : b)}
          >
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{b} Risk</div>
            <div
              className={`text-3xl font-bold mt-1 ${
                b === 'Critical'
                  ? 'text-rose-400'
                  : b === 'High'
                  ? 'text-amber-400'
                  : b === 'Medium'
                  ? 'text-yellow-400'
                  : 'text-emerald-400'
              }`}
            >
              {counts[b]}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">detected rings</div>
          </div>
        ))}
      </div>

      {/* Main Flagged Rings Table */}
      <div className="card p-0 overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-900/60">
          <div className="flex items-center space-x-2">
            <Filter size={16} className="text-cyan-400" />
            <span className="font-bold text-sm text-slate-100">Flagged Fraud Clusters</span>
            <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-300 font-mono">
              {filtered.length}
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(['All', 'Critical', 'High', 'Medium', 'Low'] as Band[]).map((b) => (
              <button
                key={b}
                className={`px-3 py-1 rounded text-xs font-medium transition ${
                  band === b
                    ? 'bg-cyan-950 text-cyan-200 border border-cyan-700'
                    : 'text-slate-400 hover:text-slate-200 bg-slate-800/60'
                }`}
                onClick={() => setBand(b)}
              >
                {b}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 font-medium">
              <tr>
                <th className="py-3 px-4">Ring ID</th>
                <th className="py-3 px-4">Risk Band</th>
                <th className="py-3 px-4 cursor-pointer" onClick={() => toggleSort('risk_score')}>
                  <span className="flex items-center gap-1.5">
                    Score <SortIcon k="risk_score" />
                  </span>
                </th>
                <th className="py-3 px-4 cursor-pointer" onClick={() => toggleSort('account_count')}>
                  <span className="flex items-center gap-1.5">
                    Accounts <SortIcon k="account_count" />
                  </span>
                </th>
                <th className="py-3 px-4 cursor-pointer" onClick={() => toggleSort('evidence_count')}>
                  <span className="flex items-center gap-1.5">
                    Signals <SortIcon k="evidence_count" />
                  </span>
                </th>
                <th className="py-3 px-4">Primary Signal</th>
                <th className="py-3 px-4">XGB Score</th>
                <th className="py-3 px-4">IF Anomaly</th>
                <th className="py-3 px-4">Rule Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filtered.map((ring) => (
                <tr
                  key={ring.ring_id}
                  onClick={() => navigate(`/ring/${ring.ring_id}`)}
                  className="cursor-pointer hover:bg-slate-800/50 transition"
                >
                  <td className="py-3 px-4 font-bold text-slate-200">{ring.ring_id}</td>
                  <td className="py-3 px-4">
                    <RiskBadge band={ring.risk_band} />
                  </td>
                  <td className="py-3 px-4" style={{ minWidth: 140 }}>
                    <ScoreBar score={ring.risk_score} band={ring.risk_band} />
                  </td>
                  <td className="py-3 px-4 text-slate-300">{ring.account_count}</td>
                  <td className="py-3 px-4 text-slate-300">{ring.evidence_count}</td>
                  <td className="py-3 px-4 font-sans">
                    {ring.top_evidence_type ? (
                      <span className="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-300 border border-slate-700">
                        {EVIDENCE_LABELS[ring.top_evidence_type] || ring.top_evidence_type}
                      </span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-cyan-400 font-bold">
                    {ring.xgb_score !== undefined && ring.xgb_score !== null
                      ? `${(ring.xgb_score * 100).toFixed(0)}%`
                      : 'N/A'}
                  </td>
                  <td className="py-3 px-4 text-indigo-400">
                    {(ring.if_score * 100).toFixed(0)}%
                  </td>
                  <td className="py-3 px-4 text-amber-400">
                    {(ring.rule_score * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 font-sans">
                    No rings match the selected filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
