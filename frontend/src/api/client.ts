// API client v3 — real-time & batch detection client

const BASE_URL = 'http://localhost:8000';
export const WS_URL = 'ws://localhost:8000/api/ws';

export interface RingListItem {
  ring_id: string;
  risk_score: number;
  risk_band: 'Critical' | 'High' | 'Medium' | 'Low';
  account_count: number;
  evidence_count: number;
  top_evidence_type: string | null;
  if_score: number;
  rule_score: number;
  xgb_score?: number | null;
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
  max_accounts_per_shared_device?: number;
  weighted_device_score?: number;
  shared_ip_count: number;
  max_accounts_per_shared_ip?: number;
  weighted_ip_score?: number;
  internal_txn_density: number;
  reciprocal_txn_count: number;
  has_cycle: boolean;
  max_cycle_length: number;
  internal_refund_ratio: number;
  refund_ratio_vs_baseline: number;
  merchant_concentration: number;
  avg_txn_velocity: number;
  creation_time_spread_seconds: number | null;
  creation_sync_ratio?: number;
  multi_signal_count?: number;
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
  xgb_score?: number | null;
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

export interface BaselinesResponse {
  baseline_1_txn_only: MetricBand;
  baseline_2_rule_only: MetricBand;
  baseline_3_if_only: MetricBand;
  baseline_4_xgb_only?: MetricBand;
  final_hybrid: MetricBand;
}

export interface MetricsResponse {
  baselines_comparison?: BaselinesResponse;
  graph_aware_detector: MetricBand;
  transaction_only_baseline: MetricBand;
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
    xgboost_used?: boolean;
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

// ── Real-Time Event & Scenario Interfaces ───────────────────────────────────

export interface LiveEventSubmitRequest {
  buyer_id: string;
  merchant_id: string;
  amount: number;
  txn_type?: 'purchase' | 'refund';
  device_id?: string;
  ip_id?: string;
  timestamp?: string;
  source?: string;
}

export interface LatencyBreakdown {
  validation?: number;
  entity_update?: number;
  graph_update: number;
  feature_extract: number;
  scoring: number;
  total: number;
}

export interface LiveUpdate {
  type?: 'live_update' | 'connected' | 'keepalive' | 'pong';
  event_id: string;
  timestamp: string;
  buyer_id: string;
  merchant_id: string;
  amount: number;
  is_refund?: boolean;
  device_id?: string;
  ip_id?: string;
  source?: string;
  risk_score: number;
  prev_risk_score: number;
  risk_delta: number;
  risk_band: 'Critical' | 'High' | 'Medium' | 'Low';
  alert_triggered: boolean;
  affected_cluster_id: number;
  changed_signals: string[];
  evidence: EvidenceItem[];
  latency_ms: LatencyBreakdown;
  cluster_stats: {
    size: number;
    xgb_score?: number | null;
    if_score: number;
    rule_score: number;
  };
  message?: string;
}

export interface ScenarioItem {
  id: string;
  name: string;
  category: string;
  is_hard_negative: boolean;
  description: string;
}

export interface ScenarioRunResponse {
  scenario_id: string;
  scenario_type: string;
  status: string;
  total_events: number;
  accounts_involved: string[];
  description: string;
  is_hard_negative: boolean;
}

export interface LiveEngineStatus {
  initialized: boolean;
  accounts: number;
  devices: number;
  ips: number;
  transactions: number;
  clusters: number;
  flagged_rings: number;
  event_stream_length: number;
  xgboost_loaded: boolean;
  if_loaded: boolean;
}

// ── Fetch Wrapper ────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export const api = {
  // Batch & Investigation endpoints
  listRings:       () => apiFetch<RingListItem[]>('/api/rings'),
  getHeroRing:     () => apiFetch<HeroRing>('/api/rings/hero'),
  getRing:         (id: string) => apiFetch<RingDetail>(`/api/rings/${id}`),
  getRingGraph:    (id: string) => apiFetch<GraphData>(`/api/rings/${id}/graph`),
  getMetrics:      () => apiFetch<MetricsResponse>('/api/metrics'),
  getBaselines:    () => apiFetch<BaselinesResponse>('/api/metrics/baselines'),
  getBenignOverlap:() => apiFetch<MetricsResponse['benign_overlap_analysis']>('/api/metrics/benign-overlap'),
  investigate:     (id: string) =>
    apiFetch<InvestigationResponse>(`/api/rings/${id}/investigate`, { method: 'POST' }),
  runPipeline:     () =>
    apiFetch<{ status: string; summary: Record<string, number> }>('/api/pipeline/run', { method: 'POST' }),

  // Real-Time Event & Scenario endpoints
  submitEvent:     (req: LiveEventSubmitRequest) =>
    apiFetch<LiveUpdate>('/api/events/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  getEventStream:  (limit = 50) =>
    apiFetch<{ events: LiveUpdate[]; total_processed: number }>(`/api/events/stream?limit=${limit}`),
  getLiveStatus:   () => apiFetch<LiveEngineStatus>('/api/events/status'),
  getRiskTimeline: (clusterId: number) =>
    apiFetch<{ cluster_id: number; timeline: Array<{ timestamp: string; risk_score: number }> }>(
      `/api/events/timeline/${clusterId}`
    ),
  getLiveRings:    () => apiFetch<{ rings: RingDetail[]; count: number }>('/api/events/rings'),
  listScenarios:   () => apiFetch<ScenarioItem[]>('/api/scenarios/list'),
  runScenario:     (scenarioType: string, delayMs = 300) =>
    apiFetch<ScenarioRunResponse>('/api/scenarios/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_type: scenarioType, inter_event_delay_ms: delayMs }),
    }),
};
