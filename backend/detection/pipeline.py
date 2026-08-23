"""
Detection pipeline orchestrator.
Runs all phases in order and persists results to data/rings.json and data/all_clusters.json.

v2: Updated synthetic legit feature generation to match 18-feature vector.
"""

import os
import json
import math
import random
from typing import Dict, Any, List, Set

import numpy as np
import pandas as pd

from detection.graph_builder import load_and_build
from detection.feature_extractor import extract_all_features, feature_vector
from detection.scorer import score_all_clusters, train_isolation_forest
from detection.evidence_builder import build_all_evidence

DATA_DIR          = os.path.join(os.path.dirname(__file__), "..", "data")
RINGS_PATH        = os.path.join(DATA_DIR, "rings.json")
ALL_CLUSTERS_PATH = os.path.join(DATA_DIR, "all_clusters.json")
FLAG_THRESHOLD    = 40.0   # must match evidence_builder.FLAG_SCORE_THRESHOLD

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def _generate_synthetic_legit_features(n: int = 300) -> List[List[float]]:
    """
    Generate synthetic feature vectors for legitimate clusters.
    Used to augment IF training when real legit clusters are sparse.

    Feature order matches feature_extractor.feature_vector() v2 (18 features):
      [cluster_size, shared_device_count, max_accounts_per_shared_device,
       weighted_device_score, shared_ip_count, max_accounts_per_shared_ip,
       weighted_ip_score, internal_txn_density, reciprocal_txn_count,
       internal_refund_ratio, refund_ratio_vs_baseline, merchant_concentration,
       avg_txn_velocity, has_cycle, max_cycle_length,
       creation_time_spread_norm, creation_sync_ratio, multi_signal_count]
    """
    features = []
    for _ in range(n):
        # Generate a mix: 70% small legit clusters (2-8), 30% large loose components (9-50)
        # Large loose components occur naturally when accounts in the general pool happen
        # to share devices/IPs transitively. The IF must learn these are NOT anomalous.
        if random.random() < 0.70:
            size = random.randint(2, 8)
        else:
            size = random.randint(9, 50)   # large clusters that must not be flagged

        # Benign: maybe 1 shared device (family biz / household)
        has_shared_dev  = random.random() < 0.4
        shared_dev_cnt  = 1 if has_shared_dev else 0
        max_acct_dev    = random.randint(2, min(size, 4)) if has_shared_dev else 0
        w_dev           = (1.0 / max(1, max_acct_dev)) if has_shared_dev else 0.0

        # Benign: maybe 1 shared IP (office / household)
        has_shared_ip   = random.random() < 0.5
        shared_ip_cnt   = 1 if has_shared_ip else 0
        max_acct_ip     = random.randint(2, min(size, 5)) if has_shared_ip else 0
        w_ip            = (0.6 / max(1, max_acct_ip)) if has_shared_ip else 0.0

        txn_density     = random.uniform(0.0, 0.10)
        recip           = 0
        refund_ratio    = random.uniform(0.01, 0.06)
        rvb             = refund_ratio / 0.03
        merch_conc      = random.uniform(0.0, 0.60)
        velocity        = random.uniform(0.01, 0.20)
        # Large time spread: accounts created days or weeks apart — not synchronized
        spread_norm     = random.uniform(0.3, 1.0)
        sync_ratio      = random.uniform(0.0, 0.3)    # not tightly synchronized
        multi           = float(sum([
            shared_dev_cnt >= 1,
            shared_ip_cnt  >= 1,
            False,   # has_cycle = False for benign
            spread_norm < 0.01,    # creation_sync (very rare for benign)
            rvb >= 3.0,
            merch_conc >= 0.75,
        ]))

        features.append([
            float(size),
            float(shared_dev_cnt),
            float(max_acct_dev),
            float(round(w_dev, 4)),
            float(shared_ip_cnt),
            float(max_acct_ip),
            float(round(w_ip, 4)),
            float(txn_density),
            float(recip),
            float(refund_ratio),
            float(rvb),
            float(merch_conc),
            float(velocity),
            0.0,            # has_cycle = False
            0.0,            # max_cycle_length = 0
            float(spread_norm),
            float(sync_ratio),
            float(multi),
        ])
    return features


def run_pipeline(force_retrain: bool = True) -> List[Dict[str, Any]]:
    """
    Full detection pipeline:
      load → graph build → cluster → features → score → evidence → persist
    Returns: list of ring evidence objects.
    """
    print("\n" + "="*60)
    print("  Coordinated Payment Abuse Detection Pipeline  v2")
    print("="*60)

    # Phase 1: Load data & build graph
    print("\n[pipeline] Phase 1: Loading data & building graph...")
    (G, H, accounts_df, devices_df, ips_df,
     txns_df, acct_devs_df, acct_ips_df) = load_and_build()

    # Phase 2: Feature extraction
    print("\n[pipeline] Phase 2: Extracting cluster features...")
    cluster_map, cluster_features = extract_all_features(
        G, H, accounts_df, txns_df, acct_devs_df, acct_ips_df
    )

    # Phase 3: Determine legitimate clusters for IF training
    fraud_accounts: Set[str] = set(
        accounts_df[accounts_df["is_fraud_ring_member"] == True]["account_id"].tolist()
    )
    legit_cluster_ids: Set[int] = set()
    for feats in cluster_features:
        if not any(m in fraud_accounts for m in feats["members"]):
            legit_cluster_ids.add(feats["cluster_id"])

    legit_fvs    = [feature_vector(f) for f in cluster_features
                    if f["cluster_id"] in legit_cluster_ids]
    synthetic_fvs = _generate_synthetic_legit_features(n=400)
    training_fvs  = legit_fvs + synthetic_fvs

    print(f"\n[pipeline] Phase 3: Training IF on {len(training_fvs)} vectors "
          f"({len(legit_fvs)} real legit + {len(synthetic_fvs)} synthetic legit)...")
    clf, scaler = train_isolation_forest(training_fvs)

    scored_clusters = score_all_clusters(cluster_features, legit_cluster_ids, clf, scaler)

    # Phase 4: Build evidence for flagged rings
    print("\n[pipeline] Phase 4: Building evidence...")
    rings = build_all_evidence(
        scored_clusters, G, H,
        accounts_df, txns_df, acct_devs_df, acct_ips_df,
        threshold=FLAG_THRESHOLD,
    )

    # Phase 5: Persist results
    os.makedirs(DATA_DIR, exist_ok=True)

    def _sanitize(obj):
        if isinstance(obj, float):
            if math.isinf(obj) or math.isnan(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(i) for i in obj]
        return obj

    rings_clean = _sanitize(rings)
    with open(RINGS_PATH, "w") as f:
        json.dump(rings_clean, f, indent=2, default=str)

    all_clusters_serializable = []
    for sc in scored_clusters:
        sc_copy = dict(sc)
        sc_copy["longest_cycle"] = sc_copy.get("longest_cycle", [])
        all_clusters_serializable.append(_sanitize(sc_copy))
    with open(ALL_CLUSTERS_PATH, "w") as f:
        json.dump(all_clusters_serializable, f, indent=2, default=str)

    print(f"\n[pipeline] Done. {len(rings)} rings flagged.")
    print(f"[pipeline]   Results: {RINGS_PATH}")
    print("="*60 + "\n")
    return rings


if __name__ == "__main__":
    run_pipeline()
