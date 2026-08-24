import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ChevronLeft, Network, Brain, AlertCircle,
  User, Store,
} from 'lucide-react';
import { api } from '../api/client';
import type { RingDetail, InvestigationResponse } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import { EvidenceCard } from '../components/EvidenceCard';

function ScoreGauge({
  score, band, ifScore, ruleScore, xgbScore,
}: {
  score: number; band: string; ifScore: number; ruleScore: number; xgbScore?: number | null;
}) {
  const COLORS: Record<string, string> = {
    Critical: '#6b4f3a', High: '#7d6048', Medium: '#987b5e', Low: '#52705a',
  };
  const color = COLORS[band] || '#6b4f3a';
  const ifPct = Math.min(100, Math.max(0, ifScore * 100));
  const rulePct = Math.min(100, Math.max(0, ruleScore * 100));
  const xgbPct = xgbScore !== undefined && xgbScore !== null ? Math.min(100, Math.max(0, xgbScore * 100)) : null;

  return (
    <div className="score-gauge-wrap">
      <div className="score-number" style={{ color }}>{score.toFixed(0)}</div>
      <div className="score-gauge-info">
        <RiskBadge band={band as any} />
        <span className="text-xs text-muted" style={{ marginTop: 4 }}>Risk Score (0–100)</span>
        <span className="text-xs text-muted" style={{ marginTop: 2, fontSize: 10 }}>0.35×IF + 0.40×XGB + 0.25×Rules</span>
      </div>
      <div style={{ flex: 1, paddingLeft: 12 }}>
        {xgbPct !== null && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span className="text-xs text-secondary">XGBoost (Supervised Signal)</span>
              <span className="text-mono" style={{ fontSize: 12, fontWeight: 600, color: '#6b4f3a' }}>{xgbPct.toFixed(1)}%</span>
            </div>
            <div className="score-bar">
              <div className="score-bar-fill" style={{
                width: `${xgbPct}%`, background: '#6b4f3a',
              }} />
            </div>
          </div>
        )}
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span className="text-xs text-secondary">Isolation Forest (Anomaly Signal)</span>
            <span className="text-mono" style={{ fontSize: 12, fontWeight: 600, color: '#8a735f' }}>{ifPct.toFixed(1)}%</span>
          </div>
          <div className="score-bar">
            <div className="score-bar-fill" style={{
              width: `${ifPct}%`, background: '#8a735f',
            }} />
          </div>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span className="text-xs text-secondary">Structural Rule Signals</span>
            <span className="text-mono" style={{ fontSize: 12, fontWeight: 600, color }}>{rulePct.toFixed(1)}%</span>
          </div>
          <div className="score-bar">
            <div className="score-bar-fill" style={{
              width: `${rulePct}%`, background: color,
            }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function InvestigationPanel({
  investigation, loading, onRun,
}: {
  ringId: string;
  investigation: InvestigationResponse | null;
  loading: boolean;
  onRun: () => void;
}) {
  // Simple markdown renderer — headings, bold, lists
  function renderMarkdown(text: string) {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      if (line.startsWith('## ')) return <h2 key={i}>{line.slice(3)}</h2>;
      if (line.startsWith('### ')) return <h3 key={i}>{line.slice(4)}</h3>;
      if (line.startsWith('**') && line.endsWith('**'))
        return <p key={i}><strong>{line.slice(2, -2)}</strong></p>;
      if (line.match(/^\d+\./))
        return <p key={i} style={{ paddingLeft: 16 }}>{line}</p>;
      if (line.startsWith('- ') || line.startsWith('* '))
        return <p key={i} style={{ paddingLeft: 16 }}>• {line.slice(2)}</p>;
      if (line.startsWith('---'))
        return <hr key={i} className="divider" />;
      if (line.trim() === '') return <div key={i} style={{ height: 8 }} />;
      // Inline bold
      const parts = line.split(/\*\*([^*]+)\*\*/g);
      if (parts.length > 1) {
        return (
          <p key={i}>
            {parts.map((p, j) => j % 2 === 1 ? <strong key={j}>{p}</strong> : p)}
          </p>
        );
      }
      return <p key={i}>{line}</p>;
    });
  }

  return (
    <div className="investigation-panel section">
      <div className="card-header" style={{
        background: 'var(--bg-elevated)',
        borderBottom: '1px solid var(--border)',
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Brain size={14} />
          AI Investigation Report
          {investigation && (
            <span className="tag" style={{ marginLeft: 4, fontSize: 10 }}>
              {investigation.model_used}
            </span>
          )}
        </span>
        <button
          id="run-investigation-btn"
          className="btn btn-primary btn-sm"
          onClick={onRun}
          disabled={loading}
        >
          {loading ? (
            <><div className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} /> Generating...</>
          ) : (
            <><Brain size={12} /> {investigation ? 'Re-run' : 'Run Investigation'}</>
          )}
        </button>
      </div>

      {!investigation && !loading && (
        <div className="empty-state" style={{ padding: 40 }}>
          <Brain size={28} color="var(--text-muted)" />
          <span className="text-muted">
            Click "Run Investigation" to generate an AI-powered analyst write-up.
          </span>
          <span className="text-xs text-muted">
            The LLM is evidence-grounded — it cannot introduce information outside the structured evidence above.
          </span>
        </div>
      )}

      {investigation && (
        <div className="investigation-body">
          {renderMarkdown(investigation.investigation)}
          <hr className="divider" />
          <div className="disclaimer-banner" style={{ marginTop: 8 }}>
            {investigation.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
}

export function RingInvestigation() {
  const { ringId } = useParams<{ ringId: string }>();
  const navigate = useNavigate();
  const [ring, setRing]           = useState<RingDetail | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [invLoading, setInvLoading] = useState(false);
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);

  useEffect(() => {
    if (!ringId) return;
    api.getRing(ringId)
      .then(setRing)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [ringId]);

  async function runInvestigation() {
    if (!ringId) return;
    setInvLoading(true);
    try {
      const result = await api.investigate(ringId);
      setInvestigation(result);
    } catch (e: any) {
      alert(`Investigation failed: ${e.message}`);
    } finally {
      setInvLoading(false);
    }
  }

  if (loading) return (
    <div className="page loading-state">
      <div className="spinner" />
      <span>Loading ring details...</span>
    </div>
  );

  if (error || !ring) return (
    <div className="page empty-state">
      <AlertCircle size={28} color="var(--risk-high)" />
      <span style={{ color: 'var(--risk-high)' }}>{error || 'Ring not found'}</span>
    </div>
  );

  const creationSpread = ring.features.creation_time_spread_seconds;
  const creationSyncLabel = creationSpread !== null && creationSpread !== undefined
    ? creationSpread < 300 ? `${creationSpread.toFixed(0)}s — Synchronized` : `${(creationSpread / 3600).toFixed(1)}h`
    : 'N/A';

  return (
    <div className="page">
      <button className="back-link" onClick={() => navigate('/')}>
        <ChevronLeft size={14} /> Risk Overview
      </button>

      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <span className="td-mono" style={{ fontSize: 20, fontWeight: 700 }}>{ring.ring_id}</span>
          <RiskBadge band={ring.risk_band} />
        </div>
        <p className="page-subtitle">
          {ring.account_count} accounts · {ring.evidence_count} evidence signals · {ring.accounts.length} members
        </p>
      </div>

      <div className="grid-2 section">
        {/* Score gauge */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Risk Score Breakdown</span>
          </div>
          <div className="card-body">
            <ScoreGauge
              score={ring.risk_score}
              band={ring.risk_band}
              ifScore={ring.if_score || 0}
              ruleScore={ring.rule_score || 0}
              xgbScore={ring.xgb_score}
            />
          </div>
        </div>

        {/* Feature snapshot */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Cluster Features</span>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              ['Cluster Size',          ring.features.cluster_size,                      ''],
              ['Shared Devices',        ring.features.shared_device_count,               ''],
              ['Shared IP Ranges',      ring.features.shared_ip_count,                   ''],
              ['Cycle Detected',        ring.features.has_cycle ? 'Yes' : 'No',          ''],
              ['Cycle Length',          ring.features.max_cycle_length || '—',           ''],
              ['Refund Ratio',          `${(ring.features.internal_refund_ratio * 100).toFixed(1)}%`, `${ring.features.refund_ratio_vs_baseline.toFixed(1)}× baseline`],
              ['Txn Density',           ring.features.internal_txn_density.toFixed(3),  ''],
              ['Merchant Concentration',`${(ring.features.merchant_concentration * 100).toFixed(0)}%`, ''],
              ['Creation Spread',       creationSyncLabel,                               ''],
            ].map(([label, value, sub]) => (
              <div key={label as string} className="stat-row">
                <span className="stat-label">{label}</span>
                <span>
                  <span className="stat-value">{value}</span>
                  {sub && <span className="text-muted text-xs" style={{ marginLeft: 6 }}>{sub}</span>}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Accounts */}
      <div className="card section">
        <div className="card-header">
          <span className="card-title"><User size={14} /> Accounts in Ring</span>
          <button
            id="view-graph-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => navigate(`/graph/${ring.ring_id}`)}
          >
            <Network size={12} /> View Graph
          </button>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {ring.account_details.map(acct => (
              <div
                key={acct.account_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 10px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                {acct.type === 'merchant' ? <Store size={12} color="var(--node-merchant)" /> : <User size={12} color="var(--node-buyer)" />}
                <span className="text-mono">{acct.account_id}</span>
                <span className="text-xs text-muted">{acct.type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Evidence */}
      <div className="card section">
        <div className="card-header">
          <span className="card-title"><AlertCircle size={14} /> Evidence Signals</span>
        </div>
        <div className="card-body">
          <div className="evidence-list">
            {ring.evidence.map((item, i) => (
              <EvidenceCard key={i} item={item} />
            ))}
          </div>
        </div>
      </div>

      {/* AI Investigation */}
      <InvestigationPanel
        ringId={ring.ring_id}
        investigation={investigation}
        loading={invLoading}
        onRun={runInvestigation}
      />
    </div>
  );
}
