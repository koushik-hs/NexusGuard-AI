"""Pydantic schemas for all API responses."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class EvidenceItem(BaseModel):
    type: str
    detail: str


class AccountDetail(BaseModel):
    account_id: str
    type: str
    created_at: str


class GraphNode(BaseModel):
    id: str
    node_type: str
    account_type: Optional[str] = None
    ip_range: Optional[str] = None
    in_ring: bool = True
    weight: Optional[float] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    suspicious: bool = False
    shared_via: Optional[str] = None
    shared_id: Optional[str] = None
    weight: Optional[float] = None


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class RingFeatures(BaseModel):
    cluster_size: int
    shared_device_count: int
    shared_ip_count: int
    internal_txn_density: float
    reciprocal_txn_count: int
    has_cycle: bool
    max_cycle_length: int
    internal_refund_ratio: float
    refund_ratio_vs_baseline: float
    merchant_concentration: float
    avg_txn_velocity: float
    creation_time_spread_seconds: Optional[float] = None
    creation_sync_ratio: Optional[float] = None
    max_accounts_per_shared_device: Optional[int] = None
    max_accounts_per_shared_ip: Optional[int] = None
    weighted_device_score: Optional[float] = None
    weighted_ip_score: Optional[float] = None
    multi_signal_count: Optional[int] = None


class RingListItem(BaseModel):
    ring_id: str
    risk_score: float
    risk_band: str
    account_count: int
    evidence_count: int
    top_evidence_type: Optional[str] = None
    if_score: float
    rule_score: float
    xgb_score: Optional[float] = None


class RingDetail(BaseModel):
    ring_id: str
    risk_score: float
    risk_band: str
    accounts: List[str]
    account_count: int
    account_details: List[AccountDetail]
    evidence: List[EvidenceItem]
    evidence_count: int
    if_score: float
    rule_score: float
    xgb_score: Optional[float] = None
    features: RingFeatures


class MetricComparison(BaseModel):
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    false_negative_rate: Optional[float] = None
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    pr_auc: Optional[float] = None
    roc_auc: Optional[float] = None
    description: Optional[str] = None


class RingTypeStats(BaseModel):
    detected: int
    total: int
    rate: float


class MetricsResponse(BaseModel):
    baselines_comparison: Optional[Dict[str, Any]] = None
    graph_aware_detector: MetricComparison
    transaction_only_baseline: MetricComparison
    ring_level: Dict[str, Any]
    benign_overlap_analysis: Dict[str, Any]
    data_summary: Dict[str, Any]
    disclaimer: str


class InvestigationResponse(BaseModel):
    ring_id: str
    investigation: str
    model_used: str
    evidence_grounded: bool
    disclaimer: str
