"""Feature ablation study — computes detection metrics for 5 feature subsets."""

import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.train import load_labeled_clusters
from detection.feature_extractor import FEATURE_NAMES
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import average_precision_score

DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
RANDOM_SEED = 42

# ── Feature subsets for ablation ───────────────────────────────────────────────
ABLATION_CONFIGS = {
    "transaction_only": [
        "internal_txn_density", "reciprocal_txn_count", "internal_refund_ratio",
        "refund_ratio_vs_baseline", "merchant_concentration", "avg_txn_velocity",
    ],
    "infrastructure_only": [
        "shared_device_count", "max_accounts_per_shared_device", "weighted_device_score",
        "shared_ip_count", "max_accounts_per_shared_ip", "weighted_ip_score",
    ],
    "graph_topology_only": [
        "has_cycle", "max_cycle_length", "cluster_size",
        "creation_time_spread_norm", "creation_sync_ratio",
    ],
    "transaction_plus_infrastructure": [
        "internal_txn_density", "reciprocal_txn_count", "internal_refund_ratio",
        "refund_ratio_vs_baseline", "merchant_concentration", "avg_txn_velocity",
        "shared_device_count", "max_accounts_per_shared_device", "weighted_device_score",
        "shared_ip_count", "max_accounts_per_shared_ip", "weighted_ip_score",
    ],
    "full_feature_set": FEATURE_NAMES,
}


def _select_features(fv, feature_indices):
    return [fv[i] for i in feature_indices]


def run_ablation():
    labeled, *_ = load_labeled_clusters()
    legit   = [c for c in labeled if not c["is_fraud"]]
    fraud   = [c for c in labeled if c["is_fraud"]]

    all_labels  = [1 if c["is_fraud"] else 0 for c in labeled]
    ablation_results = {}

    feat_idx = {name: i for i, name in enumerate(FEATURE_NAMES)}

    for config_name, feat_names in ABLATION_CONFIGS.items():
        indices = [feat_idx[f] for f in feat_names if f in feat_idx]
        if not indices:
            continue

        X_legit = np.array([_select_features(c["fv"], indices) for c in legit])
        X_all   = np.array([_select_features(c["fv"], indices) for c in labeled])

        clf = IsolationForest(n_estimators=200, contamination=0.05,
                               random_state=RANDOM_SEED, n_jobs=-1)
        clf.fit(X_legit)

        raw = clf.score_samples(X_all)
        scaler = MinMaxScaler()
        scaler.fit(clf.score_samples(X_legit).reshape(-1, 1))
        scores = [float(1.0 - scaler.transform([[s]])[0][0]) * 100 for s in raw]

        # Evaluate at threshold=40
        flagged = [s >= 40.0 for s in scores]
        tp = sum(1 for l, f in zip(all_labels, flagged) if l == 1 and f)
        fp = sum(1 for l, f in zip(all_labels, flagged) if l == 0 and f)
        fn = sum(1 for l, f in zip(all_labels, flagged) if l == 1 and not f)
        tn = sum(1 for l, f in zip(all_labels, flagged) if l == 0 and not f)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        fpr  = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        pr_auc = average_precision_score(all_labels, scores)

        ablation_results[config_name] = {
            "feature_count": len(indices),
            "features_used": feat_names,
            "precision":     round(prec, 4),
            "recall":        round(rec, 4),
            "f1":            round(f1, 4),
            "false_positive_rate": round(fpr, 4),
            "pr_auc":        round(pr_auc, 4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        }
        print(f"[ablation] {config_name:<35}: P={prec:.3f} R={rec:.3f} F1={f1:.3f} "
              f"FPR={fpr:.3f} PR-AUC={pr_auc:.3f}")

    path = os.path.join(DATA_DIR, "ablation_results.json")
    with open(path, "w") as f:
        json.dump(ablation_results, f, indent=2)
    print(f"[ablation] Results saved to {path}")
    return ablation_results


if __name__ == "__main__":
    run_ablation()
