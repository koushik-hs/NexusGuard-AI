"""
Graph builder: constructs a NetworkX heterogeneous graph from the entity tables.

Node types  : Account, Device, IP (exact)
Edge types  : ACCOUNT_USES_DEVICE, ACCOUNT_USES_IP,
              ACCOUNT_TRANSACTS_WITH_ACCOUNT,
              ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT  (derived)

v2 FIXES (root-cause of precision collapse):
  1. IP linkage now uses exact ip_id, NOT /16 range.
     The old _ip_range() bucketing merged hundreds of legitimate accounts
     sharing a carrier ISP block into one giant component, making every
     legitimate user a false positive.
  2. Edge weights reflect how many accounts share the identifier:
     fewer sharers = stronger signal (more suspicious).
  3. Identifier pools that are shared by too many accounts (>15 for devices,
     >20 for IPs) are dropped entirely — these are corporate proxies,
     carrier-grade NAT, or shared infrastructure, not fraud signals.
  4. A minimum edge weight threshold prevents very-weak IP edges from
     creating noise connections.
"""

import os
import math
from collections import defaultdict
from typing import Dict, Any, Tuple

import pandas as pd
import networkx as nx

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── Edge creation thresholds ───────────────────────────────────────────────────
# If more than this many accounts share an identifier, skip the edge entirely.
# Above these numbers the shared infrastructure is almost certainly benign
# (office NAT, campus wifi, carrier CGN, etc.).
MAX_ACCOUNTS_PER_DEVICE_FOR_EDGE = 15
MAX_ACCOUNTS_PER_IP_FOR_EDGE     = 20

# Minimum edge weight below which we still skip (avoids near-zero-weight noise).
MIN_IP_EDGE_WEIGHT = 0.08


def _device_edge_weight(n_sharing: int) -> float:
    """
    Weight for a SHARES_DEVICE edge.
    Uses 1/log2(n) so:  2→1.0,  4→0.50,  8→0.33,  15→0.26
    Device sharing is a strong signal when few accounts are involved.
    """
    if n_sharing < 2:
        return 0.0
    return 1.0 / math.log2(n_sharing)


def _ip_edge_weight(n_sharing: int) -> float:
    """
    Weight for a SHARES_IP edge.
    IP sharing is inherently weaker (ISPs, offices) so we use 0.6 base.
    2→0.60,  4→0.30,  8→0.20,  15→0.16,  20→0.14
    """
    if n_sharing < 2:
        return 0.0
    return 0.6 / math.log2(n_sharing)


def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
                          pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all entity tables from CSVs."""
    accounts   = pd.read_csv(os.path.join(DATA_DIR, "accounts.csv"))
    devices    = pd.read_csv(os.path.join(DATA_DIR, "devices.csv"))
    ips        = pd.read_csv(os.path.join(DATA_DIR, "ips.csv"))
    txns       = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"))
    acct_devs  = pd.read_csv(os.path.join(DATA_DIR, "account_devices.csv"))
    acct_ips   = pd.read_csv(os.path.join(DATA_DIR, "account_ips.csv"))
    return accounts, devices, ips, txns, acct_devs, acct_ips


def build_graph(
    accounts: pd.DataFrame,
    devices: pd.DataFrame,
    ips: pd.DataFrame,
    txns: pd.DataFrame,
    acct_devs: pd.DataFrame,
    acct_ips: pd.DataFrame,
) -> nx.MultiDiGraph:
    """
    Build the full heterogeneous entity graph.
    Returns a NetworkX MultiDiGraph with typed nodes and edges.
    """
    G = nx.MultiDiGraph()

    # ── Account nodes ─────────────────────────────────────────────────────────
    for _, row in accounts.iterrows():
        G.add_node(
            row["account_id"],
            node_type="account",
            account_type=row["type"],
            created_at=str(row["created_at"]),
            is_fraud_ring_member=bool(row.get("is_fraud_ring_member", False)),
            is_benign_overlap=bool(row.get("is_benign_overlap", False)),
            ring_id=row.get("ring_id") if pd.notna(row.get("ring_id")) else None,
        )

    # ── Device nodes ──────────────────────────────────────────────────────────
    for _, row in devices.iterrows():
        G.add_node(
            row["device_id"],
            node_type="device",
            fingerprint=str(row["fingerprint"]),
            is_fraud=bool(row.get("is_fraud", False)),
        )

    # ── IP nodes (by exact ip_id) ─────────────────────────────────────────────
    for _, row in ips.iterrows():
        node_key = f"IP_{row['ip_id']}"
        G.add_node(
            node_key,
            node_type="ip",
            ip_id=str(row["ip_id"]),
            ip_address=str(row.get("ip_address", "unknown")),
            ip_range=str(row.get("ip_range", "unknown")),
        )

    # ── ACCOUNT_USES_DEVICE edges ─────────────────────────────────────────────
    for _, row in acct_devs.iterrows():
        aid = row["account_id"]
        did = row["device_id"]
        if G.has_node(aid) and G.has_node(did):
            G.add_edge(aid, did, edge_type="ACCOUNT_USES_DEVICE")
            G.add_edge(did, aid, edge_type="DEVICE_USED_BY_ACCOUNT")

    # ── ACCOUNT_USES_IP edges ─────────────────────────────────────────────────
    for _, row in acct_ips.iterrows():
        aid     = row["account_id"]
        ip_key  = f"IP_{row['ip_id']}"
        if G.has_node(aid) and G.has_node(ip_key):
            G.add_edge(aid, ip_key, edge_type="ACCOUNT_USES_IP")
            G.add_edge(ip_key, aid, edge_type="IP_USED_BY_ACCOUNT")

    # ── ACCOUNT_TRANSACTS_WITH_ACCOUNT edges ──────────────────────────────────
    txn_agg: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total_amount": 0.0, "refund_count": 0}
    )
    for _, row in txns.iterrows():
        key = (str(row["buyer_id"]), str(row["merchant_id"]))
        txn_agg[key]["count"] += 1
        txn_agg[key]["total_amount"] += float(row["amount"])
        if row.get("is_refund"):
            txn_agg[key]["refund_count"] += 1

    for (buyer_id, merchant_id), stats in txn_agg.items():
        if G.has_node(buyer_id) and G.has_node(merchant_id):
            G.add_edge(
                buyer_id, merchant_id,
                edge_type="ACCOUNT_TRANSACTS_WITH_ACCOUNT",
                txn_count=stats["count"],
                total_amount=round(stats["total_amount"], 2),
                refund_count=stats["refund_count"],
                refund_ratio=round(stats["refund_count"] / stats["count"], 4),
            )

    # ── Derived: ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT ───────────────────────
    # Group accounts by shared device_id
    dev_to_accounts: Dict[str, set] = defaultdict(set)
    for _, row in acct_devs.iterrows():
        dev_to_accounts[str(row["device_id"])].add(str(row["account_id"]))

    # Group accounts by EXACT ip_id (v2 fix: was ip_range which caused snowballing)
    ip_to_accounts: Dict[str, set] = defaultdict(set)
    for _, row in acct_ips.iterrows():
        ip_to_accounts[str(row["ip_id"])].add(str(row["account_id"]))

    added_shares: set = set()

    # Device-sharing edges
    for device_id, acct_set in dev_to_accounts.items():
        n_sharing = len(acct_set)
        if n_sharing < 2 or n_sharing > MAX_ACCOUNTS_PER_DEVICE_FOR_EDGE:
            continue  # skip singletons and massive shared pools (>15 = likely infra)
        weight = _device_edge_weight(n_sharing)
        acct_list = sorted(acct_set)
        for i in range(len(acct_list)):
            for j in range(i + 1, len(acct_list)):
                a, b = acct_list[i], acct_list[j]
                if G.has_node(a) and G.has_node(b):
                    key = (min(a, b), max(a, b), "device", device_id)
                    if key not in added_shares:
                        attrs = dict(
                            edge_type="ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT",
                            shared_via="device",
                            shared_id=device_id,
                            weight=round(weight, 4),
                            n_sharing=n_sharing,
                        )
                        G.add_edge(a, b, **attrs)
                        G.add_edge(b, a, **attrs)
                        added_shares.add(key)

    # IP-sharing edges — using EXACT ip_id, not /16 range
    for ip_id, acct_set in ip_to_accounts.items():
        n_sharing = len(acct_set)
        if n_sharing < 2 or n_sharing > MAX_ACCOUNTS_PER_IP_FOR_EDGE:
            continue  # skip singletons and large NAT/proxy pools
        weight = _ip_edge_weight(n_sharing)
        if weight < MIN_IP_EDGE_WEIGHT:
            continue  # drop near-zero-weight edges (noise, not signal)
        acct_list = sorted(acct_set)
        for i in range(len(acct_list)):
            for j in range(i + 1, len(acct_list)):
                a, b = acct_list[i], acct_list[j]
                if G.has_node(a) and G.has_node(b):
                    key = (min(a, b), max(a, b), "ip", ip_id)
                    if key not in added_shares:
                        attrs = dict(
                            edge_type="ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT",
                            shared_via="ip",
                            shared_id=ip_id,
                            weight=round(weight, 4),
                            n_sharing=n_sharing,
                        )
                        G.add_edge(a, b, **attrs)
                        G.add_edge(b, a, **attrs)
                        added_shares.add(key)

    print(f"[graph_builder] Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def get_shares_identifier_subgraph(G: nx.MultiDiGraph) -> nx.Graph:
    """
    Extract an undirected subgraph containing only Account nodes connected
    by ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT edges.
    Edge weights are preserved; when two accounts share both a device and an
    IP the higher-weight edge is kept (max-weight per pair).
    """
    H = nx.Graph()
    for n, data in G.nodes(data=True):
        if data.get("node_type") == "account":
            H.add_node(n, **data)

    for u, v, data in G.edges(data=True):
        if data.get("edge_type") == "ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT":
            if (G.nodes[u].get("node_type") == "account"
                    and G.nodes[v].get("node_type") == "account"):
                if H.has_edge(u, v):
                    # Keep the higher-weight edge (device beats IP)
                    if data.get("weight", 0) > H[u][v].get("weight", 0):
                        for k, val in data.items():
                            H[u][v][k] = val
                else:
                    H.add_edge(u, v, **data)
    return H


def load_and_build() -> Tuple[nx.MultiDiGraph, nx.Graph,
                               pd.DataFrame, pd.DataFrame,
                               pd.DataFrame, pd.DataFrame,
                               pd.DataFrame, pd.DataFrame]:
    """Convenience: load CSVs and build both graphs."""
    accounts, devices, ips, txns, acct_devs, acct_ips = load_data()
    G = build_graph(accounts, devices, ips, txns, acct_devs, acct_ips)
    H = get_shares_identifier_subgraph(G)
    print(f"[graph_builder] Shares-identifier subgraph: "
          f"{H.number_of_nodes()} accounts, {H.number_of_edges()} sharing edges")
    return G, H, accounts, devices, ips, txns, acct_devs, acct_ips
