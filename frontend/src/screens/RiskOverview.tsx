import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ChevronUp, ChevronDown, Filter } from 'lucide-react';
import { api } from '../api/client';
import type { RingListItem } from '../api/client';
import { RiskBadge, ScoreBar } from '../components/RiskBadge';

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
  const [rings, setRings]       = useState<RingListItem[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [band, setBand]         = useState<Band>('All');
  const [sortKey, setSortKey]   = useState<SortKey>('risk_score');
  const [sortAsc, setSortAsc]   = useState(false);

  useEffect(() => {
    api.listRings()
      .then(setRings)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let r = band === 'All' ? rings : rings.filter(x => x.risk_band === band);
    r = [...r].sort((a, b) => {
      const delta = (a[sortKey] as number) - (b[sortKey] as number);
      return sortAsc ? delta : -delta;
    });
    return r;
  }, [rings, band, sortKey, sortAsc]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    rings.forEach(r => c[r.risk_band]++);
    return c;
  }, [rings]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(v => !v);
    else { setSortKey(key); setSortAsc(false); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span style={{ opacity: 0.3 }}><ChevronDown size={12} /></span>;
    return sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />;
  }

  if (loading) return (
    <div className="page loading-state">
      <div className="spinner" />
      <span>Loading ring detection results...</span>
    </div>
  );

  if (error) return (
    <div className="page empty-state">
      <AlertTriangle size={32} color="var(--risk-high)" />
      <span style={{ color: 'var(--risk-high)' }}>API Error: {error}</span>
      <span className="text-muted text-sm">Is the backend running on port 8000?</span>
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Risk Overview</h1>
        <p className="page-subtitle">
          {rings.length} fraud rings detected across the monitored entity graph
        </p>
      </div>

      {/* Band summary row */}
      <div className="metrics-grid section" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {(['Critical', 'High', 'Medium', 'Low'] as const).map(b => (
          <div
            key={b}
            className="metric-card"
            style={{ cursor: 'pointer', borderColor: band === b ? `var(--risk-${b.toLowerCase()})` : undefined }}
            onClick={() => setBand(b === band ? 'All' : b)}
          >
            <div className="metric-label">{b} Risk</div>
            <div
              className="metric-value"
              style={{ fontSize: 28, color: `var(--risk-${b.toLowerCase()})` }}
            >
              {counts[b]}
            </div>
            <div className="metric-sub">rings</div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="card section">
        <div className="card-header">
          <span className="card-title">
            <Filter size={14} />
            Flagged Rings
            <span className="tag" style={{ marginLeft: 4 }}>{filtered.length}</span>
          </span>
          <div className="filter-bar">
            {(['All', 'Critical', 'High', 'Medium', 'Low'] as Band[]).map(b => (
              <button
                key={b}
                id={`filter-${b.toLowerCase()}`}
                className={`filter-btn ${band === b ? `active-${b.toLowerCase()}` : ''}`}
                onClick={() => setBand(b)}
              >
                {b}
              </button>
            ))}
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ring ID</th>
                <th>Risk Band</th>
                <th onClick={() => toggleSort('risk_score')} style={{ cursor: 'pointer' }}>
                  <span className="flex items-center gap-2">Score <SortIcon k="risk_score" /></span>
                </th>
                <th onClick={() => toggleSort('account_count')} style={{ cursor: 'pointer' }}>
                  <span className="flex items-center gap-2">Accounts <SortIcon k="account_count" /></span>
                </th>
                <th onClick={() => toggleSort('evidence_count')} style={{ cursor: 'pointer' }}>
                  <span className="flex items-center gap-2">Signals <SortIcon k="evidence_count" /></span>
                </th>
                <th>Primary Signal</th>
                <th>IF Score</th>
                <th>Rule Score</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(ring => (
                <tr
                  key={ring.ring_id}
                  id={`ring-row-${ring.ring_id}`}
                  onClick={() => navigate(`/ring/${ring.ring_id}`)}
                >
                  <td className="td-mono">{ring.ring_id}</td>
                  <td><RiskBadge band={ring.risk_band} /></td>
                  <td style={{ minWidth: 140 }}>
                    <ScoreBar score={ring.risk_score} band={ring.risk_band} />
                  </td>
                  <td className="td-mono">{ring.account_count}</td>
                  <td className="td-mono">{ring.evidence_count}</td>
                  <td>
                    {ring.top_evidence_type
                      ? <span className="tag">{EVIDENCE_LABELS[ring.top_evidence_type] || ring.top_evidence_type}</span>
                      : <span className="text-muted">—</span>
                    }
                  </td>
                  <td className="td-mono" style={{ color: 'var(--text-muted)' }}>
                    {(ring.if_score * 100).toFixed(0)}
                  </td>
                  <td className="td-mono" style={{ color: 'var(--text-muted)' }}>
                    {(ring.rule_score * 100).toFixed(0)}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
                    No rings match the selected filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="disclaimer-banner">
        <strong>Note:</strong> All results are derived from a synthetic dataset generated with injected ring patterns.
        Results demonstrate the detection methodology. Flagged rings require human analyst review before any action.
      </div>
    </div>
  );
}
