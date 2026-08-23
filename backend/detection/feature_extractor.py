"""
Feature extractor: detects candidate clusters and computes per-cluster features.

v2 changes:
  - Louvain split threshold lowered from 15 to 8 (split smaller components too)
  - Added max_accounts_per_shared_device / max_accounts_per_shared_ip features
    (captures "how concentrated" device/IP sharing is, not just how many)
  - Added weighted_device_score / weighted_ip_score from edge weights in H
  - Added multi_signal_count (how many distinct signal types are active)
  - Added creation_sync_ratio (fraction of accounts in tight creation window)
  - IP features now use exact ip_id column (not ip_range) for shared-IP counting

Cluster detection strategy:
  1. Connected components on the SHARES_IDENTIFIER subgraph (fast, deterministic)
  2. Louvain community detection within components >= LOUVAIN_SPLIT_THRESHOLD
     (splits loose rings into tighter sub-clusters)
"""

import os
import math
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Set, Tuple

import pandas as pd
import numpy as np
import networkx as nx

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False
    print("[feature_extractor] WARNING: python-louvain not installed. "
          "Falling back to connected components only.")

PLATFORM_REFUND_RATE     = 0.03    # 3% baseline
MIN_COMPONENT_SIZE       = 2       # ignore singletons
MAX_CYCLE_LENGTH         = 6       # bound cycle search
LOUVAIN_SPLIT_THRESHOLD  = 20      # raised: don't split rings that have incidental IP neighbors
CREATION_SYNC_WINDOW_S   = 300     # 5-minute window for sync detection


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        return datetime(2024, 1, 1)


def detect_clusters(H: nx.Graph) -> Dict[str, int]:
    """
    Detect clusters in the shares-identifier subgraph H.
    Returns: account_id → cluster_id (integer). -1 = unclustered singleton.
    """
    cluster_map: Dict[str, int] = {}
    cluster_id = 0

    components = list(nx.connected_components(H))
    for comp in components:
        if len(comp) < MIN_COMPONENT_SIZE:
            for node in comp:
                cluster_map[node] = -1
            continue

        if HAS_LOUVAIN and len(comp) >= LOUVAIN_SPLIT_THRESHOLD:
            subH      = H.subgraph(comp).copy()
            partition = community_louvain.best_partition(subH, random_state=42)
            sub_ids   = set(partition.values())
            sub_id_map = {sid: (cluster_id + i) for i, sid in enumerate(sorted(sub_ids))}
            for node, sid in partition.items():
                cluster_map[node] = sub_id_map[sid]
            cluster_id += len(sub_ids)
        else:
            for node in comp:
                cluster_map[node] = cluster_id
            cluster_id += 1

    return cluster_map


def compute_cluster_features(
    cluster_id: int,
    members: List[str],
    G: nx.MultiDiGraph,
    H: nx.Graph,
    accounts_df: pd.DataFrame,
    txns_df: pd.DataFrame,
    acct_devs_df: pd.DataFrame,
    acct_ips_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute all features for a single cluster."""
    member_set: Set[str] = set(members)
    n = len(members)

    # ── Structural: shared devices ────────────────────────────────────────────
    dev_df   = acct_devs_df[acct_devs_df["account_id"].isin(member_set)]
    dev_grp  = dev_df.groupby("device_id")["account_id"].nunique()
    shared_device_count           = int((dev_grp >= 2).sum())
    max_accounts_per_shared_device = int(dev_grp.max()) if len(dev_grp) > 0 else 0

    # ── Structural: shared IPs (using exact ip_id if available) ───────────────
    ip_df = acct_ips_df[acct_ips_df["account_id"].isin(member_set)]
    group_col = "ip_id" if "ip_id" in ip_df.columns else "ip_range"
    if len(ip_df) > 0:
        ip_grp  = ip_df.groupby(group_col)["account_id"].nunique()
        shared_ip_count             = int((ip_grp >= 2).sum())
        max_accounts_per_shared_ip  = int(ip_grp.max())
    else:
        shared_ip_count            = 0
        max_accounts_per_shared_ip = 0

    # ── Weighted graph signal scores (from H edge weights) ────────────────────
    # Sum of edge weights for device-sharing and IP-sharing edges within cluster
    weighted_device_sum = 0.0
    weighted_ip_sum     = 0.0
    for u, v, data in H.edges(members, data=True):
        if u in member_set and v in member_set:
            w = data.get("weight", 0.0)
            if data.get("shared_via") == "device":
                weighted_device_sum += w
            elif data.get("shared_via") in ("ip", "ip_range"):
                weighted_ip_sum += w
    # Normalize per cluster member so size doesn't dominate
    weighted_device_score = weighted_device_sum / max(n, 1)
    weighted_ip_score     = weighted_ip_sum     / max(n, 1)

    # ── Transaction analysis ──────────────────────────────────────────────────
    internal_txns = txns_df[
        txns_df["buyer_id"].isin(member_set) & txns_df["merchant_id"].isin(member_set)
    ]
    all_cluster_txns = txns_df[
        txns_df["buyer_id"].isin(member_set) | txns_df["merchant_id"].isin(member_set)
    ]

    max_possible_edges  = n * (n - 1)
    internal_edge_count = len(internal_txns)
    internal_txn_density = (internal_edge_count / max_possible_edges
                            if max_possible_edges > 0 else 0.0)

    # Reciprocal transactions: (A→B) and (B→A) both exist
    pairs              = set(zip(internal_txns["buyer_id"], internal_txns["merchant_id"]))
    reciprocal_count   = sum(1 for (a, b) in pairs if (b, a) in pairs) // 2

    # Refund ratio
    total_txns_count  = len(all_cluster_txns)
    refund_count      = int(all_cluster_txns["is_refund"].sum()) if "is_refund" in all_cluster_txns else 0
    internal_refund_ratio     = refund_count / total_txns_count if total_txns_count > 0 else 0.0
    refund_ratio_vs_baseline  = internal_refund_ratio / PLATFORM_REFUND_RATE

    # Merchant concentration
    merch_txns = txns_df[txns_df["merchant_id"].isin(member_set)]
    if len(merch_txns) > 0:
        vol_per_merchant    = merch_txns.groupby("merchant_id")["amount"].sum()
        top_merchant_vol    = float(vol_per_merchant.max())
        total_vol           = float(vol_per_merchant.sum())
        merchant_concentration = top_merchant_vol / total_vol if total_vol > 0 else 0.0
        top_merchant_id     = str(vol_per_merchant.idxmax())
    else:
        merchant_concentration = 0.0
        top_merchant_id        = None

    # Transaction velocity (txns/account/day)
    TXN_WINDOW_DAYS  = 90
    avg_txn_velocity = total_txns_count / (TXN_WINDOW_DAYS * max(n, 1))

    # ── Cycle detection ───────────────────────────────────────────────────────
    mini_G = nx.DiGraph()
    for _, row in internal_txns.iterrows():
        if row["buyer_id"] in member_set and row["merchant_id"] in member_set:
            mini_G.add_edge(row["buyer_id"], row["merchant_id"])

    has_cycle      = False
    max_cycle_len  = 0
    longest_cycle: List[str] = []
    try:
        for cycle in nx.simple_cycles(mini_G):
            if 2 <= len(cycle) <= MAX_CYCLE_LENGTH:
                has_cycle = True
                if len(cycle) > max_cycle_len:
                    max_cycle_len  = len(cycle)
                    longest_cycle  = cycle
    except Exception:
        pass

    # ── Temporal: account creation synchronization ────────────────────────────
    acct_rows      = accounts_df[accounts_df["account_id"].isin(member_set)]
    creation_times = [_parse_dt(t) for t in acct_rows["created_at"]]
    if len(creation_times) >= 2:
        ts_list = sorted([t.timestamp() for t in creation_times])
        creation_time_spread_seconds = float(ts_list[-1] - ts_list[0])
        # Fraction created within CREATION_SYNC_WINDOW_S of the group median
        median_ts = ts_list[len(ts_list) // 2]
        synced    = sum(1 for t in ts_list if abs(t - median_ts) <= CREATION_SYNC_WINDOW_S)
        creation_sync_ratio = synced / len(ts_list)
    else:
        creation_time_spread_seconds = float("inf")
        creation_sync_ratio          = 0.0

    # ── Multi-signal count ────────────────────────────────────────────────────
    # Count how many distinct suspicious signal types are active.
    # A high count means many independent corroborating signals — very hard to explain benignly.
    multi_signal_count = sum([
        shared_device_count >= 1,
        shared_ip_count     >= 1,
        has_cycle,
        creation_time_spread_seconds <= CREATION_SYNC_WINDOW_S,
        refund_ratio_vs_baseline >= 3.0,
        merchant_concentration  >= 0.75,
    ])

    return {
        "cluster_id":                    cluster_id,
        "members":                       members,
        "cluster_size":                  n,
        # Shared-identifier features
        "shared_device_count":           shared_device_count,
        "max_accounts_per_shared_device": max_accounts_per_shared_device,
        "shared_ip_count":               shared_ip_count,
        "max_accounts_per_shared_ip":    max_accounts_per_shared_ip,
        "weighted_device_score":         round(weighted_device_score, 4),
        "weighted_ip_score":             round(weighted_ip_score, 4),
        # Transaction features
        "internal_txn_density":          round(internal_txn_density, 4),
        "reciprocal_txn_count":          reciprocal_count,
        "internal_refund_ratio":         round(internal_refund_ratio, 4),
        "refund_ratio_vs_baseline":      round(refund_ratio_vs_baseline, 4),
        "merchant_concentration":        round(merchant_concentration, 4),
        "top_merchant_id":               top_merchant_id,
        "avg_txn_velocity":              round(avg_txn_velocity, 4),
        "total_txn_count":               total_txns_count,
        "total_refund_count":            refund_count,
        # Cycle features
        "has_cycle":                     has_cycle,
        "max_cycle_length":              max_cycle_len,
        "longest_cycle":                 longest_cycle,
        # Temporal features
        "creation_time_spread_seconds":  creation_time_spread_seconds,
        "creation_sync_ratio":           round(creation_sync_ratio, 4),
        # Multi-signal aggregation
        "multi_signal_count":            multi_signal_count,
    }


def extract_all_features(
    G: nx.MultiDiGraph,
    H: nx.Graph,
    accounts_df: pd.DataFrame,
    txns_df: pd.DataFrame,
    acct_devs_df: pd.DataFrame,
    acct_ips_df: pd.DataFrame,
) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """
    Full feature extraction pipeline.
    Returns:
      cluster_map:     account_id → cluster_id
      cluster_features: list of feature dicts per cluster
    """
    print("[feature_extractor] Detecting clusters...")
    cluster_map = detect_clusters(H)

    clusters_by_id: Dict[int, List[str]] = defaultdict(list)
    for acct_id, cid in cluster_map.items():
        if cid >= 0:
            clusters_by_id[cid].append(acct_id)

    print(f"[feature_extractor] Found {len(clusters_by_id)} clusters (excluding singletons)")

    cluster_features = []
    for cid, members in clusters_by_id.items():
        feats = compute_cluster_features(
            cid, members, G, H,
            accounts_df, txns_df, acct_devs_df, acct_ips_df
        )
        cluster_features.append(feats)

    # Print cluster size distribution for diagnostics
    sizes = sorted([f["cluster_size"] for f in cluster_features], reverse=True)
    if sizes:
        print(f"[feature_extractor] Cluster sizes: max={sizes[0]}, "
              f"p90={sizes[int(len(sizes)*0.1)]}, median={sizes[len(sizes)//2]}, "
              f"total clusters={len(sizes)}")

    return cluster_map, cluster_features


def feature_vector(feats: Dict[str, Any]) -> List[float]:
    """
    Extract the numeric feature vector for the Isolation Forest.
    This is the stable contract with scorer.py and ml/train.py.

    v2: 18 features (was 12). New features: max_accounts_per_shared_device,
    max_accounts_per_shared_ip, weighted_device_score, weighted_ip_score,
    multi_signal_count, creation_sync_ratio.
    """
    spread = feats["creation_time_spread_seconds"]
    spread_norm = float(min(spread, 604800) / 604800) if spread != float("inf") else 1.0

    return [
        # size
        float(feats["cluster_size"]),
        # device sharing
        float(feats["shared_device_count"]),
        float(feats["max_accounts_per_shared_device"]),
        float(feats["weighted_device_score"]),
        # IP sharing
        float(feats["shared_ip_count"]),
        float(feats["max_accounts_per_shared_ip"]),
        float(feats["weighted_ip_score"]),
        # transaction signals
        float(feats["internal_txn_density"]),
        float(feats["reciprocal_txn_count"]),
        float(feats["internal_refund_ratio"]),
        float(feats["refund_ratio_vs_baseline"]),
        float(feats["merchant_concentration"]),
        float(feats["avg_txn_velocity"]),
        # cycle
        float(1 if feats["has_cycle"] else 0),
        float(feats["max_cycle_length"]),
        # temporal
        spread_norm,
        float(feats["creation_sync_ratio"]),
        # aggregated
        float(feats["multi_signal_count"]),
    ]


# Feature names for ablation study and interpretability
FEATURE_NAMES = [
    "cluster_size",
    "shared_device_count",
    "max_accounts_per_shared_device",
    "weighted_device_score",
    "shared_ip_count",
    "max_accounts_per_shared_ip",
    "weighted_ip_score",
    "internal_txn_density",
    "reciprocal_txn_count",
    "internal_refund_ratio",
    "refund_ratio_vs_baseline",
    "merchant_concentration",
    "avg_txn_velocity",
    "has_cycle",
    "max_cycle_length",
    "creation_time_spread_norm",
    "creation_sync_ratio",
    "multi_signal_count",
]
