"""
Evidence builder: produces a structured evidence object per flagged ring.

This is the stable interface between the detection engine and everything
downstream (API, frontend, LLM layer).

Evidence object shape:
{
  "ring_id": "R017",
  "risk_score": 92.0,
  "risk_band": "Critical",
  "accounts": ["A101", "A104", ...],
  "account_details": [{"account_id": ..., "type": ..., "created_at": ...}, ...],
  "evidence": [
    {"type": "shared_device", "detail": "4 accounts share device D0017"},
    ...
  ],
  "graph_summary": {
    "nodes": [...],
    "edges": [...]
  }
}
"""

import os
from typing import Dict, List, Any, Set

import pandas as pd
import networkx as nx

PLATFORM_REFUND_RATE = 0.03
TXN_WINDOW_DAYS = 90
CREATION_SYNC_WINDOW_SECONDS = 300
MERCHANT_CONC_THRESHOLD = 0.75
REFUND_ELEVATION_THRESHOLD = 3.0
FLAG_SCORE_THRESHOLD = 40.0   # minimum score to be reported as a flagged ring


def _format_ids(ids: List[str], max_show: int = 4) -> str:
    if len(ids) <= max_show:
        return ", ".join(ids)
    return ", ".join(ids[:max_show]) + f" (+{len(ids) - max_show} more)"


def build_evidence(
    scored_cluster: Dict[str, Any],
    G: nx.MultiDiGraph,
    H: nx.Graph,
    accounts_df: pd.DataFrame,
    txns_df: pd.DataFrame,
    acct_devs_df: pd.DataFrame,
    acct_ips_df: pd.DataFrame,
    ring_counter: int,
) -> Dict[str, Any]:
    """Build the complete evidence object for one cluster."""
    members: List[str] = scored_cluster["members"]
    member_set: Set[str] = set(members)
    risk_score = scored_cluster["risk_score"]
    risk_band  = scored_cluster["risk_band"]
    ring_id    = f"R{ring_counter:03d}"

    evidence_items: List[Dict[str, str]] = []

    # â”€â”€ 1. Shared device evidence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    dev_df = acct_devs_df[acct_devs_df["account_id"].isin(member_set)]
    dev_groups = dev_df.groupby("device_id")["account_id"].apply(list)
    for device_id, accts in dev_groups.items():
        if len(accts) >= 2:
            evidence_items.append({
                "type": "shared_device",
                "detail": f"{len(accts)} accounts share device {device_id}: {_format_ids(sorted(accts))}",
            })

    # â”€â”€ 2. Shared IP evidence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ip_df = acct_ips_df[acct_ips_df["account_id"].isin(member_set)].copy()
    if "ip_range" in ip_df.columns:
        ip_groups = ip_df.groupby("ip_range")["account_id"].apply(list)
        for ip_range, accts in ip_groups.items():
            if len(accts) >= 2 and ip_range != "unknown":
                evidence_items.append({
                    "type": "shared_ip",
                    "detail": f"{len(accts)} accounts share IP range {ip_range}: {_format_ids(sorted(accts))}",
                })

    # â”€â”€ 3. Refund ratio evidence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    all_txns = txns_df[
        txns_df["buyer_id"].isin(member_set) | txns_df["merchant_id"].isin(member_set)
    ]
    total = len(all_txns)
    if total > 0:
        refund_count = int(all_txns["is_refund"].sum())
        ratio = refund_count / total
        if ratio >= PLATFORM_REFUND_RATE * REFUND_ELEVATION_THRESHOLD:
            evidence_items.append({
                "type": "refund_ratio",
                "detail": (f"Refund ratio {ratio:.1%} vs {PLATFORM_REFUND_RATE:.1%} "
                           f"platform baseline ({ratio / PLATFORM_REFUND_RATE:.1f}Ã— elevated). "
                           f"{refund_count} refunds out of {total} transactions."),
            })

    # â”€â”€ 4. Cycle / circular flow evidence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if scored_cluster.get("has_cycle") and scored_cluster.get("longest_cycle"):
        cycle = scored_cluster["longest_cycle"]
        cycle_str = " â†’ ".join(cycle) + f" â†’ {cycle[0]}"
        evidence_items.append({
            "type": "circular_flow",
            "detail": f"Circular transaction flow detected (length {len(cycle)}): {cycle_str}",
        })

    # â”€â”€ 5. Transaction concentration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    conc = scored_cluster.get("merchant_concentration", 0.0)
    if conc >= MERCHANT_CONC_THRESHOLD:
        top_m = scored_cluster.get("top_merchant_id")
        evidence_items.append({
            "type": "transaction_concentration",
            "detail": (f"{conc:.0%} of transaction volume flows to "
                       f"merchant {top_m}. "
                       f"High concentration suggests coordinated funneling."),
        })

    # â”€â”€ 6. Creation time synchronization â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    spread = scored_cluster.get("creation_time_spread_seconds", float("inf"))
    if spread <= CREATION_SYNC_WINDOW_SECONDS and len(members) >= 2:
        evidence_items.append({
            "type": "temporal_sync",
            "detail": (f"{len(members)} accounts created within "
                       f"{int(spread)} seconds of each other â€” "
                       f"suggests coordinated batch registration."),
        })

    # â”€â”€ 7. Transaction velocity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    velocity = scored_cluster.get("avg_txn_velocity", 0.0)
    if velocity > 1.0:   # > 1 txn/account/day
        evidence_items.append({
            "type": "high_velocity",
            "detail": (f"Average transaction velocity: {velocity:.2f} txns/account/day "
                       f"({velocity / 0.1:.1f}Ã— platform average)."),
        })

    # â”€â”€ Account details â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    acct_rows = accounts_df[accounts_df["account_id"].isin(member_set)]
    account_details = []
    for _, row in acct_rows.iterrows():
        account_details.append({
            "account_id": row["account_id"],
            "type": row["type"],
            "created_at": str(row["created_at"]),
        })

    # â”€â”€ Graph summary (for Graph Explorer) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Nodes: all accounts in ring + their devices + IPs
    graph_nodes = []
    graph_edges = []
    seen_nodes: Set[str] = set()

    for aid in members:
        if aid not in seen_nodes and G.has_node(aid):
            node_data = G.nodes[aid]
            graph_nodes.append({
                "id": aid,
                "node_type": "account",
                "account_type": node_data.get("account_type", "unknown"),
                "in_ring": True,
            })
            seen_nodes.add(aid)

    # Devices connected to ring accounts
    for _, row in acct_devs_df[acct_devs_df["account_id"].isin(member_set)].iterrows():
        did = row["device_id"]
        if did not in seen_nodes and G.has_node(did):
            graph_nodes.append({
                "id": did,
                "node_type": "device",
                "in_ring": True,
            })
            seen_nodes.add(did)
            graph_edges.append({
                "source": row["account_id"], "target": did,
                "edge_type": "ACCOUNT_USES_DEVICE",
                "suspicious": True,
            })

    # IP ranges
    for _, row in acct_ips_df[acct_ips_df["account_id"].isin(member_set)].iterrows():
        ip_range = str(row.get("ip_range", "unknown"))
        node_key = f"IP_RANGE_{ip_range}"
        if node_key not in seen_nodes and G.has_node(node_key):
            graph_nodes.append({
                "id": node_key,
                "node_type": "ip_range",
                "ip_range": ip_range,
                "in_ring": True,
            })
            seen_nodes.add(node_key)
            graph_edges.append({
                "source": row["account_id"], "target": node_key,
                "edge_type": "ACCOUNT_USES_IP",
                "suspicious": True,
            })

    # SHARES_IDENTIFIER edges between ring accounts
    for u, v, data in H.edges(members, data=True):
        if u in member_set and v in member_set:
            graph_edges.append({
                "source": u, "target": v,
                "edge_type": "SHARES_IDENTIFIER",
                "shared_via": data.get("shared_via"),
                "shared_id": data.get("shared_id"),
                "suspicious": True,
            })

    # Transaction edges between ring accounts
    internal_txns = txns_df[
        txns_df["buyer_id"].isin(member_set) & txns_df["merchant_id"].isin(member_set)
    ]
    seen_txn_pairs: Set = set()
    for _, row in internal_txns.iterrows():
        pair = (row["buyer_id"], row["merchant_id"])
        if pair not in seen_txn_pairs:
            graph_edges.append({
                "source": row["buyer_id"], "target": row["merchant_id"],
                "edge_type": "TRANSACTION",
                "suspicious": False,
            })
            seen_txn_pairs.add(pair)

    return {
        "ring_id": ring_id,
        "risk_score": risk_score,
        "risk_band": risk_band,
        "cluster_id": scored_cluster["cluster_id"],
        "accounts": sorted(members),
        "account_count": len(members),
        "account_details": account_details,
        "evidence": evidence_items,
        "evidence_count": len(evidence_items),
        "if_score": scored_cluster.get("if_score", 0),
        "rule_score": scored_cluster.get("rule_score", 0),
        "xgb_score": scored_cluster.get("xgb_score"),
        "features": {
            "cluster_size": scored_cluster["cluster_size"],
            "shared_device_count": scored_cluster["shared_device_count"],
            "max_accounts_per_shared_device": scored_cluster.get("max_accounts_per_shared_device", 0),
            "weighted_device_score": scored_cluster.get("weighted_device_score", 0.0),
            "shared_ip_count": scored_cluster["shared_ip_count"],
            "max_accounts_per_shared_ip": scored_cluster.get("max_accounts_per_shared_ip", 0),
            "weighted_ip_score": scored_cluster.get("weighted_ip_score", 0.0),
            "internal_txn_density": scored_cluster["internal_txn_density"],
            "reciprocal_txn_count": scored_cluster["reciprocal_txn_count"],
            "has_cycle": scored_cluster["has_cycle"],
            "max_cycle_length": scored_cluster["max_cycle_length"],
            "internal_refund_ratio": scored_cluster["internal_refund_ratio"],
            "refund_ratio_vs_baseline": scored_cluster["refund_ratio_vs_baseline"],
            "merchant_concentration": scored_cluster["merchant_concentration"],
            "avg_txn_velocity": scored_cluster["avg_txn_velocity"],
            "creation_time_spread_seconds": scored_cluster["creation_time_spread_seconds"],
            "creation_sync_ratio": scored_cluster.get("creation_sync_ratio", 0.0),
            "multi_signal_count": scored_cluster.get("multi_signal_count", 0),
        },
        "graph": {
            "nodes": graph_nodes,
            "edges": graph_edges,
        },
    }


def build_all_evidence(
    scored_clusters: List[Dict[str, Any]],
    G: nx.MultiDiGraph,
    H: nx.Graph,
    accounts_df: pd.DataFrame,
    txns_df: pd.DataFrame,
    acct_devs_df: pd.DataFrame,
    acct_ips_df: pd.DataFrame,
    threshold: float = FLAG_SCORE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Build evidence for all clusters above the flag threshold."""
    flagged = [c for c in scored_clusters if c["risk_score"] >= threshold]
    # Sort by risk score descending
    flagged.sort(key=lambda x: x["risk_score"], reverse=True)

    results = []
    for i, cluster in enumerate(flagged, start=1):
        ev = build_evidence(
            cluster, G, H,
            accounts_df, txns_df, acct_devs_df, acct_ips_df,
            ring_counter=i
        )
        results.append(ev)
        print(f"[evidence_builder] Ring {ev['ring_id']}: score={ev['risk_score']}, "
              f"band={ev['risk_band']}, accounts={ev['account_count']}, "
              f"evidence items={ev['evidence_count']}")

    print(f"[evidence_builder] âœ“ {len(results)} rings flagged "
          f"(threshold={threshold})")
    return results

