// API client v2 — all backend calls go through here

const BASE_URL = 'http://localhost:8000';

export interface RingListItem {
  ring_id: string;
  risk_score: number;
  risk_band: 'Critical' | 'High' | 'Medium' | 'Low';
  account_count: number;
  evidence_count: number;
  top_evidence_type: string | null;
  if_score: number;
  rule_score: number;
}

export interface EvidenceItem {
  type: string;
  detail: string;
}

export interface AccountDetail {
  account_id: string;
  type: string;
  created_at: string;
}

export interface RingFeatures {
  cluster_size: number;
  shared_device_count: number;
  max_accounts_per_shared_device: number;
  weighted_device_score: number;
  shared_ip_count: number;
  max_accounts_per_shared_ip: number;
  weighted_ip_score: number;
  internal_txn_density: number;
  reciprocal_txn_count: number;
  has_cycle: boolean;
  max_cycle_length: number;
  internal_refund_ratio: number;
  refund_ratio_vs_baseline: number;
  merchant_concentration: number;
  avg_txn_velocity: number;
  creation_time_spread_seconds: number | null;
  creation_sync_ratio: number;
  multi_signal_count: number;
}

export interface RingDetail {
  ring_id: string;
  risk_score: number;
  risk_band: 'Critical' | 'High' | 'Medium' | 'Low';
  accounts: string[];
  account_count: number;
  account_details: AccountDetail[];
  evidence: EvidenceItem[];
  evidence_count: number;
  if_score: number;
  rule_score: number;
  features: RingFeatures;
}

export interface GraphNode {
  id: string;
  node_type: string;
  account_type?: string;
  ip_range?: string;
  in_ring: boolean;
  weight?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  edge_type: string;
  suspicious: boolean;
  shared_via?: string;
  shared_id?: string;
  weight?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface MetricBand {
  precision: number;
  recall: number;
  f1: number;
  false_positive_rate: number;
  false_negative_rate?: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
  pr_auc?: number;
  roc_auc?: number;
  description?: string;
}

// Legacy alias
export type MetricComparison = MetricBand;

export interface BaselinesResponse {
  baseline_1_txn_only: MetricBand;
  baseline_2_rule_only: MetricBand;
  baseline_3_if_only: MetricBand;
  final_hybrid: MetricBand;
}

export interface MetricsResponse {
  // v2: full baselines comparison
  baselines_comparison?: BaselinesResponse;
  // legacy keys (for backward compat)
  graph_aware_detector: MetricComparison;
  transaction_only_baseline: MetricComparison;
  ring_level: {
    total_gt_rings: number;
    rings_detected: number;
    overall_ring_recall: number;
    detection_rate_by_type: Record<string, { detected: number; total: number; rate: number }>;
  };
  benign_overlap_analysis: {
    total_benign_overlap_accounts: number;
    flagged_benign_overlap_accounts: number;
    benign_overlap_fpr: number;
    by_type?: Record<string, { total: number; flagged: number; fpr: number }>;
    note: string;
  };
  data_summary: {
    total_accounts: number;
    fraud_ring_accounts: number;
    legitimate_accounts: number;
    benign_overlap_accounts: number;
    rings_flagged_by_detector: number;
  };
  disclaimer: string;
}

export interface InvestigationResponse {
  ring_id: string;
  investigation: string;
  model_used: string;
  evidence_grounded: boolean;
  disclaimer: string;
}

export interface HeroRing extends RingDetail {
  is_hero: boolean;
  hero_overlap: number;
  hero_members: string[];
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export const api = {
  listRings:      () => apiFetch<RingListItem[]>('/api/rings'),
  getHeroRing:    () => apiFetch<HeroRing>('/api/rings/hero'),
  getRing:        (id: string) => apiFetch<RingDetail>(`/api/rings/${id}`),
  getRingGraph:   (id: string) => apiFetch<GraphData>(`/api/rings/${id}/graph`),
  getMetrics:     () => apiFetch<MetricsResponse>('/api/metrics'),
  getBaselines:   () => apiFetch<BaselinesResponse>('/api/metrics/baselines'),
  getBenignOverlap: () => apiFetch<MetricsResponse['benign_overlap_analysis']>('/api/metrics/benign-overlap'),
  investigate:    (id: string) =>
    apiFetch<InvestigationResponse>(`/api/rings/${id}/investigate`, { method: 'POST' }),
  runPipeline:    () => apiFetch<{ status: string; summary: Record<string, number> }>('/api/pipeline/run', { method: 'POST' }),
};
