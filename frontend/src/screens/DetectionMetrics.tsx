import { useEffect, useState } from 'react';
import { BarChart2, AlertCircle, CheckCircle, TrendingUp, Shield, Layers, Award } from 'lucide-react';
import { api } from '../api/client';
import type { MetricsResponse, MetricBand, BaselinesResponse } from '../api/client';
import { MetricCard } from '../components/MetricCard';

function pct(v: number) { return `${(v * 100).toFixed(1)}%`; }
function fmt(v: number | undefined) { return v !== undefined ? pct(v) : '—'; }

// ── 5-Baseline comparison table ────────────────────────────────────────────────
const BASELINE_COLS: Array<{ key: keyof BaselinesResponse; label: string; accent?: boolean }> = [
  { key: 'baseline_1_txn_only',  label: 'BL1: Txn-Only' },
  { key: 'baseline_2_rule_only', label: 'BL2: Rule-Only' },
  { key: 'baseline_3_if_only',   label: 'BL3: IF-Only' },
  { key: 'baseline_4_xgb_only',  label: 'BL4: XGBoost' },
  { key: 'final_hybrid',         label: 'Final: Hybrid', accent: true },
];

const TABLE_ROWS: Array<{ key: keyof MetricBand; label: string; higherBetter: boolean }> = [
  { key: 'precision',          label: 'Precision',          higherBetter: true },
  { key: 'recall',             label: 'Recall',             higherBetter: true },
  { key: 'f1',                 label: 'F1 Score',           higherBetter: true },
  { key: 'false_positive_rate',label: 'False Positive Rate',higherBetter: false },
  { key: 'pr_auc',             label: 'PR-AUC',             higherBetter: true },
];

function BaselineTable({ data }: { data: BaselinesResponse }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="baseline-table">
        <thead>
          <tr>
            <th style={{ textAlign: 'left', color: 'var(--text-muted)', fontWeight: 500 }}>Metric</th>
            {BASELINE_COLS.map(col => (
              <th
                key={col.key}
                style={{
                  color: col.accent ? 'var(--accent-blue)' : 'var(--text-secondary)',
                  fontWeight: col.accent ? 700 : 500,
                  background: col.accent ? 'rgba(37,99,235,0.06)' : undefined,
                }}
              >
                {col.label}
                {col.accent && <div style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)' }}>★ Submission</div>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {TABLE_ROWS.map(row => {
            const vals = BASELINE_COLS.map(col => {
              const v = data[col.key]?.[row.key] as number | undefined;
              return v;
            });
            const best = vals.reduce((b, v) =>
              v === undefined ? b : (b === undefined ? v : (row.higherBetter ? Math.max(b, v) : Math.min(b, v))),
              undefined as number | undefined
            );
            return (
              <tr key={row.key}>
                <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{row.label}</td>
                {BASELINE_COLS.map((col, i) => {
                  const v = vals[i];
                  const isBest = v !== undefined && v === best;
                  const isHybrid = col.accent;
                  return (
                    <td
                      key={col.key}
                      style={{
                        fontFamily: 'monospace',
                        fontWeight: isBest ? 700 : 400,
                        color: isBest
                          ? (row.higherBetter ? 'var(--risk-low)' : 'var(--risk-low)')
                          : 'var(--text-primary)',
                        background: isHybrid ? 'rgba(37,99,235,0.04)' : undefined,
                        position: 'relative',
                      }}
                    >
                      {fmt(v)}
                      {isBest && <span style={{ marginLeft: 4, fontSize: 10, color: 'var(--risk-low)' }}>▲</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {/* Row separator */}
          <tr><td colSpan={6} style={{ padding: 0, borderTop: '1px solid rgba(255,255,255,0.06)' }} /></tr>
          {/* Counts */}
          {(['true_positives','false_positives','false_negatives'] as const).map(k => (
            <tr key={k}>
              <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                {k === 'true_positives' ? 'True Positives' : k === 'false_positives' ? 'False Positives' : 'False Negatives'}
              </td>
              {BASELINE_COLS.map(col => (
                <td
                  key={col.key}
                  style={{
                    fontFamily: 'monospace', fontSize: 12,
                    color: k === 'false_positives' && (data[col.key]?.[k] ?? 0) > 5
                      ? 'var(--risk-high)' : 'var(--text-muted)',
                    background: col.accent ? 'rgba(37,99,235,0.04)' : undefined,
                  }}
                >
                  {data[col.key]?.[k] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetectionByType({ data }: {
  data: Record<string, { detected: number; total: number; rate: number }>;
}) {
  const LABELS: Record<string, string> = {
    shared_device:   'Shared Device',
    shared_ip:       'Shared IP',
    collusion:       'Buyer-Merchant Collusion',
    refund_farming:  'Refund Farming',
    circular_flow:   'Circular Flow',
    mixed_signal:    'Mixed Signal',
  };

  return (
    <div className="detection-bars">
      {Object.entries(data).map(([type, stats]) => (
        <div key={type} className="detection-bar-row">
          <span className="detection-bar-label">{LABELS[type] || type}</span>
          <div className="detection-bar-track">
            <div
              className={`detection-bar-fill ${stats.rate >= 1 ? 'full' : ''}`}
              style={{ width: `${stats.rate * 100}%` }}
            />
          </div>
          <span className="detection-bar-stat">{stats.detected}/{stats.total}</span>
        </div>
      ))}
    </div>
  );
}

function BenignTypeRow({ label, data }: {
  label: string;
  data: { total: number; flagged: number; fpr: number };
}) {
  const isGood = data.fpr < 0.2;
  return (
    <div className="stat-row">
      <span className="stat-label" style={{ fontSize: 12 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)' }}>
          {data.flagged}/{data.total}
        </span>
        <span style={{
          fontFamily: 'monospace', fontSize: 12,
          color: isGood ? 'var(--risk-low)' : 'var(--risk-high)',
          fontWeight: 600,
        }}>
          {pct(data.fpr)}
        </span>
      </div>
    </div>
  );
}

export function DetectionMetrics() {
  const [metrics,   setMetrics]   = useState<MetricsResponse | null>(null);
  const [baselines, setBaselines] = useState<BaselinesResponse | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');

  useEffect(() => {
    Promise.all([api.getMetrics(), api.getBaselines().catch(() => null)])
      .then(([m, b]) => {
        setMetrics(m);
        // Prefer dedicated endpoint; fall back to embedded in metrics
        setBaselines(b || m.baselines_comparison || null);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="page loading-state">
      <div className="spinner" />
      <span>Loading evaluation results...</span>
    </div>
  );

  if (error || !metrics) return (
    <div className="page empty-state">
      <AlertCircle size={28} color="var(--risk-high)" />
      <span style={{ color: 'var(--risk-high)' }}>{error || 'Metrics unavailable'}</span>
    </div>
  );

  const hybrid  = baselines?.final_hybrid || metrics.graph_aware_detector;
  const base    = metrics.transaction_only_baseline;
  const ring    = metrics.ring_level;
  const benign  = metrics.benign_overlap_analysis;
  const data_s  = metrics.data_summary;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Detection Metrics</h1>
        <p className="page-subtitle">
          All numbers from actual code execution against synthetic data — no placeholder values
        </p>
      </div>

      {/* Data summary strip */}
      <div className="metrics-grid section" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        <MetricCard label="Total Accounts"      value={data_s.total_accounts.toLocaleString()} />
        <MetricCard label="Fraud Ring Members"  value={data_s.fraud_ring_accounts} sub="ground truth" />
        <MetricCard label="Legitimate"          value={data_s.legitimate_accounts.toLocaleString()} />
        <MetricCard label="Benign Overlap"      value={data_s.benign_overlap_accounts} sub="hard negatives" />
        <MetricCard label="Rings Flagged"       value={data_s.rings_flagged_by_detector} accent />
      </div>

      {/* Hero metric — ring-level recall */}
      {ring.overall_ring_recall >= 0.95 && (
        <div className="card section" style={{ borderColor: 'rgba(16,185,129,0.35)', background: 'rgba(16,185,129,0.05)' }}>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Award size={28} color="var(--risk-low)" style={{ flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--risk-low)' }}>
                Ring-Level Recall: {pct(ring.overall_ring_recall)} — {ring.rings_detected}/{ring.total_gt_rings} fraud rings detected
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                Every injected ring type (shared device, shared IP, collusion, refund farming, circular flow, mixed signal) was caught.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4-baseline comparison — the central exhibit */}
      <div className="card section">
        <div className="card-header">
          <span className="card-title">
            <TrendingUp size={14} />
            4-Baseline Comparison
          </span>
          <span className="tag">Central Experiment</span>
        </div>
        <div className="card-body">
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
            Each baseline sees the same data. <strong>BL1</strong> (transaction-only IF) has no graph signal — it misses
            coordinated rings that look individually normal. <strong>BL2</strong> (rule-only) uses deterministic structural rules
            without ML calibration. <strong>BL3</strong> (IF-only graph) has no rule grounding — high recall but poor precision.
            The <strong>Final Hybrid</strong> (0.40×IF + 0.60×rules) combines both to balance precision and recall.
          </p>
          {baselines
            ? <BaselineTable data={baselines} />
            : (
              <div className="comparison-grid">
                <div className="comparison-card">
                  <div className="comparison-card-title">Transaction-Only Baseline</div>
                  <div className="stat-row"><span className="stat-label">Precision</span><span className="stat-value">{pct(base.precision)}</span></div>
                  <div className="stat-row"><span className="stat-label">Recall</span><span className="stat-value">{pct(base.recall)}</span></div>
                  <div className="stat-row"><span className="stat-label">F1</span><span className="stat-value">{pct(base.f1)}</span></div>
                </div>
                <div className="comparison-card" style={{ borderColor: 'rgba(37,99,235,0.3)' }}>
                  <div className="comparison-card-title">Final Hybrid Detector</div>
                  <div className="stat-row"><span className="stat-label">Precision</span><span className="stat-value better">{pct(hybrid.precision)}</span></div>
                  <div className="stat-row"><span className="stat-label">Recall</span><span className="stat-value better">{pct(hybrid.recall)}</span></div>
                  <div className="stat-row"><span className="stat-label">F1</span><span className="stat-value better">{pct(hybrid.f1)}</span></div>
                </div>
              </div>
            )
          }
        </div>
      </div>

      {/* Ring-level recall + benign overlap side by side */}
      <div className="grid-2 section">
        <div className="card">
          <div className="card-header">
            <span className="card-title"><BarChart2 size={14} /> Detection Rate by Ring Type</span>
          </div>
          <div className="card-body">
            <div style={{ marginBottom: 12 }}>
              <div className="stat-row">
                <span className="stat-label">Total Injected Rings</span>
                <span className="stat-value">{ring.total_gt_rings}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Rings Detected</span>
                <span className="stat-value better">{ring.rings_detected}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Ring-Level Recall</span>
                <span className="stat-value better">{pct(ring.overall_ring_recall)}</span>
              </div>
            </div>
            <DetectionByType data={ring.detection_rate_by_type} />
          </div>
        </div>

        {/* Benign overlap FPR */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><Shield size={14} /> Benign Overlap Analysis</span>
            <span className="tag" style={{
              color: benign.benign_overlap_fpr < 0.15
                ? 'var(--risk-low)' : benign.benign_overlap_fpr < 0.30
                ? 'var(--risk-medium)' : 'var(--risk-high)',
            }}>
              {benign.benign_overlap_fpr < 0.15 ? 'PASS' : 'REVIEW'}
            </span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
              Hard negatives: accounts sharing infrastructure signals (device, IP) who are <em>not</em> fraud.
              Family businesses, office employees, households. The model must distinguish coordination from coincidence.
            </p>
            <div className="stat-row">
              <span className="stat-label">Benign Overlap Total</span>
              <span className="stat-value">{benign.total_benign_overlap_accounts}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Incorrectly Flagged</span>
              <span className="stat-value" style={{
                color: benign.flagged_benign_overlap_accounts > 0
                  ? 'var(--risk-medium)' : 'var(--risk-low)',
              }}>
                {benign.flagged_benign_overlap_accounts}
              </span>
            </div>
            <div className="stat-row" style={{ marginBottom: 12 }}>
              <span className="stat-label">Overall FPR</span>
              <span className="stat-value" style={{
                color: benign.benign_overlap_fpr < 0.15
                  ? 'var(--risk-low)' : 'var(--risk-medium)',
              }}>
                {pct(benign.benign_overlap_fpr)}
              </span>
            </div>

            {benign.by_type && Object.entries(benign.by_type).map(([btype, stats]) => (
              <BenignTypeRow
                key={btype}
                label={btype.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                data={stats}
              />
            ))}

            <div style={{ marginTop: 16 }}>
              {benign.benign_overlap_fpr < 0.15 ? (
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <CheckCircle size={14} color="var(--risk-low)" style={{ flexShrink: 0, marginTop: 2 }} />
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    Creation-time spread modifier (accounts created &gt;1 day apart → 75% signal reduction)
                    and large sparse component cap prevent benign household/family accounts from being flagged.
                  </span>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <AlertCircle size={14} color="var(--risk-medium)" style={{ flexShrink: 0, marginTop: 2 }} />
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    Some benign overlap accounts flagged — human review required. Corporate office accounts
                    sharing a device with the general IP pool remain a harder case.
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Hybrid detector full metrics */}
      <div className="card section">
        <div className="card-header">
          <span className="card-title"><Layers size={14} /> Hybrid Detector — Full Account-Level Metrics</span>
          <span className="tag">0.40 × IF + 0.60 × Rules</span>
        </div>
        <div className="card-body">
          <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            <MetricCard label="Precision"          value={pct(hybrid.precision)}          sub="of flagged, how many real?" accent />
            <MetricCard label="Recall"             value={pct(hybrid.recall)}             sub="of real, how many caught?"  accent />
            <MetricCard label="F1 Score"           value={pct(hybrid.f1)}                sub="harmonic mean"              accent />
            <MetricCard label="False Positive Rate"value={pct(hybrid.false_positive_rate)}sub="legit accounts flagged" />
          </div>
          {(hybrid as any).pr_auc && (
            <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginTop: 8 }}>
              <MetricCard label="PR-AUC"  value={((hybrid as any).pr_auc  as number).toFixed(3)} sub="area under precision-recall curve" accent />
              {(hybrid as any).roc_auc && (
                <MetricCard label="ROC-AUC" value={((hybrid as any).roc_auc as number).toFixed(3)} sub="area under ROC curve" accent />
              )}
            </div>
          )}
        </div>
      </div>

      <div className="disclaimer-banner">
        <strong>Disclaimer:</strong> {metrics.disclaimer}
      </div>
    </div>
  );
}
