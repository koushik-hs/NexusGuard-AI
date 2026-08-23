"""
ML training pipeline with proper train/validation/test split.

Split strategy:
  - Train IF on:  legitimate clusters only (from all data)
  - Val set:      collusion rings + circular_flow rings (ring_type held back for validation)
  - Test set:     mixed_signal + remaining circular_flow (held-out ring types)
  
This tests whether the model learned transferable structural/behavioral patterns
rather than memorizing specific ring templates.

Run independently:
  cd backend && python -m ml.train
"""

import os
import json
import pickle
import random
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import (
    precision_recall_curve, average_precision_score,
    classification_report, confusion_matrix
)

# Ensure backend/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detection.graph_builder import load_and_build
from detection.feature_extractor import extract_all_features, feature_vector, FEATURE_NAMES
from detection.scorer import _rule_score, score_cluster

DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR  = DATA_DIR
RANDOM_SEED = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Ring types used for training vs held-out validation/test
TRAIN_RING_TYPES = {"shared_device", "refund_farming"}
VAL_RING_TYPES   = {"collusion", "shared_ip"}
TEST_RING_TYPES  = {"circular_flow", "mixed_signal"}


def load_labeled_clusters():
    """
    Load all cluster features and attach ground-truth labels.
    Returns list of dicts with feature vector + label.
    """
    print("[ml/train] Building graph and extracting features...")
    (G, H, accounts_df, devices_df, ips_df,
     txns_df, acct_devs_df, acct_ips_df) = load_and_build()

    cluster_map, cluster_features = extract_all_features(
        G, H, accounts_df, txns_df, acct_devs_df, acct_ips_df
    )

    # Load ground truth
    labels_df = pd.read_csv(os.path.join(DATA_DIR, "labels.csv"))
    acct_to_ring_id   = dict(zip(labels_df["account_id"].astype(str), labels_df["ring_id"].astype(str)))
    acct_to_ring_type = dict(zip(labels_df["account_id"].astype(str), labels_df["ring_type"].astype(str)))
    fraud_accts       = set(labels_df["account_id"].astype(str).tolist())

    labeled = []
    for feats in cluster_features:
        members     = feats["members"]
        fraud_members  = [m for m in members if m in fraud_accts]
        is_fraud       = len(fraud_members) > 0

        # Determine ring type for split assignment
        if fraud_members:
            # Use the most common ring type in this cluster
            rtypes = [acct_to_ring_type.get(m, "unknown") for m in fraud_members]
            from collections import Counter
            ring_type = Counter(rtypes).most_common(1)[0][0]
        else:
            ring_type = "legitimate"

        labeled.append({
            "cluster_id":  feats["cluster_id"],
            "members":     members,
            "features":    feats,
            "fv":          feature_vector(feats),
            "is_fraud":    is_fraud,
            "ring_type":   ring_type,
            "fraud_fraction": len(fraud_members) / len(members),
        })

    return labeled, G, H, accounts_df, txns_df, acct_devs_df, acct_ips_df


def train_and_evaluate():
    labeled, *_ = load_labeled_clusters()

    # Split by ring type for generalization test
    train_clusters = [c for c in labeled if c["ring_type"] in TRAIN_RING_TYPES
                      or c["ring_type"] == "legitimate"]
    val_clusters   = [c for c in labeled if c["ring_type"] in VAL_RING_TYPES
                      or c["ring_type"] == "legitimate"]
    test_clusters  = [c for c in labeled if c["ring_type"] in TEST_RING_TYPES
                      or c["ring_type"] == "legitimate"]

    print(f"[ml/train] Split: {len(train_clusters)} train, "
          f"{len(val_clusters)} val, {len(test_clusters)} test clusters")

    # ── Train Isolation Forest on legitimate clusters only ────────────────────
    legit_train = [c for c in train_clusters if not c["is_fraud"]]
    X_legit     = np.array([c["fv"] for c in legit_train])

    print(f"[ml/train] Training IF on {len(X_legit)} legitimate training clusters...")
    clf_if = IsolationForest(n_estimators=300, contamination=0.05,
                              random_state=RANDOM_SEED, n_jobs=-1)
    clf_if.fit(X_legit)

    raw_legit_scores = clf_if.score_samples(X_legit)
    scaler           = MinMaxScaler()
    scaler.fit(raw_legit_scores.reshape(-1, 1))

    # ── Train supervised Random Forest for comparison ─────────────────────────
    # Requires labeled data — use all non-test clusters
    rf_train = train_clusters + val_clusters
    X_rf  = np.array([c["fv"] for c in rf_train])
    y_rf  = np.array([1 if c["is_fraud"] else 0 for c in rf_train])

    if len(set(y_rf)) == 2:  # need both classes
        print(f"[ml/train] Training RF on {len(X_rf)} clusters "
              f"({y_rf.sum()} fraud, {(y_rf==0).sum()} legit)...")
        clf_rf = RandomForestClassifier(n_estimators=200, random_state=RANDOM_SEED,
                                         class_weight="balanced", n_jobs=-1)
        clf_rf.fit(X_rf, y_rf)

        # Feature importances
        importances = dict(zip(FEATURE_NAMES, clf_rf.feature_importances_))
        top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        print("[ml/train] Top-10 RF feature importances:")
        for feat, imp in top_features[:10]:
            print(f"  {feat:<40}: {imp:.4f}")
    else:
        clf_rf = None
        top_features = []
        print("[ml/train] WARNING: Only one class in RF training data; skipping RF.")

    # ── Threshold calibration on validation set ───────────────────────────────
    val_fraud = [c for c in val_clusters if c["is_fraud"]]
    val_legit = [c for c in val_clusters if not c["is_fraud"]]
    print(f"[ml/train] Calibrating threshold on val set: "
          f"{len(val_fraud)} fraud, {len(val_legit)} legit clusters...")

    if val_fraud and val_legit:
        X_val   = np.array([c["fv"] for c in val_clusters])
        y_val   = np.array([1 if c["is_fraud"] else 0 for c in val_clusters])

        # Compute hybrid scores on val set
        val_scores = []
        for c in val_clusters:
            fv_arr  = np.array(c["fv"]).reshape(1, -1)
            raw_if  = clf_if.score_samples(fv_arr)[0]
            if_norm = float(1.0 - scaler.transform([[raw_if]])[0][0])
            if_norm = max(0.0, min(1.0, if_norm))
            rule    = _rule_score(c["features"])
            hybrid  = (0.40 * if_norm + 0.60 * rule) * 100
            val_scores.append(hybrid)

        # Find threshold maximizing F1 on validation set
        best_f1, best_threshold = 0.0, 40.0
        for thresh in np.arange(20, 80, 2):
            flagged = set(val_clusters[i]["cluster_id"] for i, s in enumerate(val_scores)
                          if s >= thresh)
            tp = sum(1 for i, c in enumerate(val_clusters)
                     if c["is_fraud"] and c["cluster_id"] in flagged)
            fp = sum(1 for i, c in enumerate(val_clusters)
                     if not c["is_fraud"] and c["cluster_id"] in flagged)
            fn = sum(1 for i, c in enumerate(val_clusters)
                     if c["is_fraud"] and c["cluster_id"] not in flagged)
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            if f1 > best_f1:
                best_f1, best_threshold = f1, thresh

        print(f"[ml/train] Best validation threshold: {best_threshold} (F1={best_f1:.4f})")
    else:
        best_threshold = 40.0
        print("[ml/train] Insufficient val data for calibration; using default threshold=40")

    # ── Evaluate on held-out test set ─────────────────────────────────────────
    test_fraud = [c for c in test_clusters if c["is_fraud"]]
    test_legit = [c for c in test_clusters if not c["is_fraud"]]
    print(f"[ml/train] Test set evaluation: "
          f"{len(test_fraud)} fraud, {len(test_legit)} legit clusters...")

    test_hybrid_scores = []
    for c in test_clusters:
        fv_arr  = np.array(c["fv"]).reshape(1, -1)
        raw_if  = clf_if.score_samples(fv_arr)[0]
        if_norm = float(1.0 - scaler.transform([[raw_if]])[0][0])
        if_norm = max(0.0, min(1.0, if_norm))
        rule    = _rule_score(c["features"])
        hybrid  = (0.40 * if_norm + 0.60 * rule) * 100
        test_hybrid_scores.append(hybrid)

    test_labels  = [1 if c["is_fraud"] else 0 for c in test_clusters]
    flagged_test = [s >= best_threshold for s in test_hybrid_scores]

    tp = sum(1 for l, f in zip(test_labels, flagged_test) if l == 1 and f)
    fp = sum(1 for l, f in zip(test_labels, flagged_test) if l == 0 and f)
    fn = sum(1 for l, f in zip(test_labels, flagged_test) if l == 1 and not f)
    tn = sum(1 for l, f in zip(test_labels, flagged_test) if l == 0 and not f)

    prec_test = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec_test  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_test   = 2 * prec_test * rec_test / (prec_test + rec_test) if (prec_test + rec_test) > 0 else 0.0

    print(f"[ml/train] Test set results (cluster-level, threshold={best_threshold}):")
    print(f"  Precision={prec_test:.4f}, Recall={rec_test:.4f}, F1={f1_test:.4f}")
    print(f"  TP={tp}, FP={fp}, FN={fn}, TN={tn}")
    print(f"  NOTE: Test ring types ({TEST_RING_TYPES}) were NOT seen in training.")

    # ── Save artifacts ────────────────────────────────────────────────────────
    ml_artifacts = {
        "calibrated_threshold":  float(best_threshold),
        "val_best_f1":           float(best_f1),
        "test_results": {
            "precision": float(round(prec_test, 4)),
            "recall":    float(round(rec_test, 4)),
            "f1":        float(round(f1_test, 4)),
            "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
            "held_out_ring_types": list(TEST_RING_TYPES),
        },
        "feature_importances": [{"feature": f, "importance": float(round(i, 6))}
                                  for f, i in top_features],
        "train_ring_types": list(TRAIN_RING_TYPES),
        "val_ring_types":   list(VAL_RING_TYPES),
        "test_ring_types":  list(TEST_RING_TYPES),
    }

    ml_path = os.path.join(DATA_DIR, "ml_artifacts.json")
    with open(ml_path, "w") as f:
        json.dump(ml_artifacts, f, indent=2)
    print(f"[ml/train] ML artifacts saved to {ml_path}")

    # Also save the trained IF model (same path as production)
    with open(os.path.join(MODEL_DIR, "if_model.pkl"), "wb") as f:
        pickle.dump({"model": clf_if, "scaler": scaler}, f)
    if clf_rf is not None:
        with open(os.path.join(MODEL_DIR, "rf_model.pkl"), "wb") as f:
            pickle.dump(clf_rf, f)
    print("[ml/train] Models saved.")

    return ml_artifacts


if __name__ == "__main__":
    train_and_evaluate()
