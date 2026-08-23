"""
Hybrid risk scorer.

v2 changes:
  - Rule score now uses max_accounts_per_shared_device / cluster_size instead of
    shared_device_count / cluster_size. This captures "all 5 accounts share ONE device"
    (highly suspicious) vs "30 accounts share 8 devices" (average 3.75/device, less so).
  - Added multi_signal_bonus: clusters with 3+ distinct signal types get a boost.
  - Added weak_cluster_penalty: no device sharing, no IP sharing, no cycle → cap score.
  - Updated feature vector to 18 features (matches feature_extractor v2).

Score = 0.40 × IF_score_normalized + 0.60 × rule_score_normalized

Risk bands (heuristic defaults — stated plainly, not data-derived):
  Low      0–39
  Medium   40–64
  High     65–84
  Critical 85–100
"""

import os
import pickle
from typing import Dict, List, Any, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

from detection.feature_extractor import feature_vector

MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_PATH = os.path.join(MODEL_DIR, "if_model.pkl")

# ── Risk band thresholds ───────────────────────────────────────────────────────
BAND_THRESHOLDS = [(85, "Critical"), (65, "High"), (40, "Medium"), (0, "Low")]

# ── Rule-score weights ────────────────────────────────────────────────────────
RULE_WEIGHTS = {
    "shared_device":          0.30,   # device sharing: strongest single signal
    "shared_ip":              0.15,   # IP sharing: real but weaker
    "cycle":                  0.25,   # circular flow: very hard to explain benignly
    "creation_sync":          0.10,   # tight creation window: batch account creation
    "refund_elevation":       0.10,   # refund rate >> platform baseline
    "merchant_concentration": 0.10,   # funneling volume to one merchant
}

# Thresholds for rule signals
CREATION_SYNC_WINDOW_SECONDS = 300    # 5-minute tight creation window
REFUND_ELEVATION_THRESHOLD   = 3.0   # 3× platform baseline
MERCHANT_CONC_THRESHOLD      = 0.75  # 75% of volume to one merchant


def _rule_score(feats: Dict[str, Any]) -> float:
    """
    Compute a rule-based score in [0, 1] from deterministic structural signals.

    v2 key change: device signal now uses max_accounts_per_shared_device / cluster_size.
    This distinguishes:
      - 5 accounts all on 1 device → ratio=1.0 → strong signal
      - 30 accounts with 8 shared devices (max 4/device) → ratio=4/30=0.13 → weak signal
    The old version used shared_device_count/cluster_size which would give
    8/30=0.27 for the second case — worse at discriminating.
    """
    score = 0.0
    n     = feats["cluster_size"]

    # ── Hard pre-check: large sparse components are almost certainly not fraud ──
    # If a cluster has many accounts but almost no internal transactions and no
    # cycle, it is a "loose component" formed by transitive coincidental sharing
    # (e.g. A shares device with B, B shares IP with C, C shares device with D…).
    # Even a high IF anomaly score should not flag these — anomalousness here
    # just means "we haven't seen a cluster this large", not "this is fraud".
    spread = feats.get("creation_time_spread_seconds", float("inf"))
    rvb    = feats.get("refund_ratio_vs_baseline", 0.0)
    max_dev = feats.get("max_accounts_per_shared_device", 0)
    max_ip  = feats.get("max_accounts_per_shared_ip", 0)

    is_large_sparse = (
        n > 15
        and not feats["has_cycle"]
        and feats.get("internal_txn_density", 0) < 0.03
        and rvb < 3.0
        and feats.get("reciprocal_txn_count", 0) == 0
    )

    # ── Creation-time spread modifier ─────────────────────────────────────────
    # Fraud rings: accounts created within seconds/minutes of each other.
    # Household / family business: accounts created independently over months.
    # When spread > 30 days AND cluster is small with no cycle → reduce
    # infrastructure signals — the "shared device" is a home computer, not a
    # fraudster's batch-registration tool.
    DAYS_1_S   = 1 * 86400     # fraud rings create accounts in seconds; 1 day = benign
    is_benign_spread = (
        spread != float("inf")
        and spread > DAYS_1_S
        and n <= 8
        and not feats["has_cycle"]
        and rvb < 3.0
    )
    infra_scale = 0.25 if is_benign_spread else 1.0   # reduce to 25% of signal if benign spread

    # Shared device signal
    if n > 0 and max_dev >= 2:
        device_ratio = min(max_dev / n, 1.0)
        score += device_ratio * RULE_WEIGHTS["shared_device"] * infra_scale

    # Shared IP signal
    if n > 0 and max_ip >= 2:
        ip_ratio = min(max_ip / n, 1.0)
        score += ip_ratio * RULE_WEIGHTS["shared_ip"] * infra_scale

    # Cycle signal: circular money flow — NOT reduced by spread (cycles are structural)
    if feats["has_cycle"]:
        cycle_bonus = min(feats["max_cycle_length"] / 6.0, 1.0)
        score      += cycle_bonus * RULE_WEIGHTS["cycle"]

    # Creation synchronization — the tighter the better
    if spread != float("inf") and spread <= CREATION_SYNC_WINDOW_SECONDS:
        sync_score = 1.0 - (spread / CREATION_SYNC_WINDOW_SECONDS)
        score     += sync_score * RULE_WEIGHTS["creation_sync"]

    # Refund elevation
    if rvb >= REFUND_ELEVATION_THRESHOLD:
        refund_score = min((rvb - REFUND_ELEVATION_THRESHOLD) / 10.0 + 0.5, 1.0)
        score       += refund_score * RULE_WEIGHTS["refund_elevation"]

    # Merchant concentration
    conc = feats.get("merchant_concentration", 0.0)
    if conc >= MERCHANT_CONC_THRESHOLD:
        conc_score = (conc - MERCHANT_CONC_THRESHOLD) / (1.0 - MERCHANT_CONC_THRESHOLD)
        score     += conc_score * RULE_WEIGHTS["merchant_concentration"]

    # Multi-signal bonus: 3+ independent signals → strong corroboration
    multi = feats.get("multi_signal_count", 0)
    if multi >= 3 and not is_benign_spread:   # don't bonus benign-spread clusters
        score += min((multi - 2) * 0.05, 0.15)

    # Weak cluster penalty: no device, no IP, no cycle → hard cap
    if (max_dev < 2 and max_ip < 2 and not feats["has_cycle"]):
        score = min(score, 0.35)

    return min(score, 1.0)


def train_isolation_forest(
    legit_features: List[List[float]]
) -> Tuple[IsolationForest, MinMaxScaler]:
    """
    Train an IsolationForest on legitimate-population cluster feature vectors.
    Contamination set to 0.05 (expect ~5% anomalous training examples).
    """
    X = np.array(legit_features)
    if len(X) == 0:
        raise ValueError("No legitimate clusters to train on.")

    clf = IsolationForest(
        n_estimators=200, contamination=0.05,
        random_state=42, n_jobs=-1
    )
    clf.fit(X)

    raw_scores = clf.score_samples(X)
    scaler     = MinMaxScaler()
    scaler.fit(raw_scores.reshape(-1, 1))

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf, "scaler": scaler}, f)

    print(f"[scorer] IsolationForest trained on {len(X)} legitimate clusters. "
          f"Model saved to {MODEL_PATH}")
    return clf, scaler


def load_isolation_forest() -> Tuple[IsolationForest, MinMaxScaler]:
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)
    return data["model"], data["scaler"]


def score_cluster(
    feats: Dict[str, Any],
    clf: IsolationForest,
    scaler: MinMaxScaler,
) -> Dict[str, Any]:
    """Compute the hybrid risk score for one cluster."""
    fv  = np.array(feature_vector(feats)).reshape(1, -1)

    raw_if               = clf.score_samples(fv)[0]
    if_score_normalized  = float(1.0 - scaler.transform([[raw_if]])[0][0])
    if_score_normalized  = max(0.0, min(1.0, if_score_normalized))

    rule_score_normalized = _rule_score(feats)

    combined    = 0.40 * if_score_normalized + 0.60 * rule_score_normalized
    score_0_100 = round(combined * 100, 1)

    # Hard cap: large sparse components cannot be flagged regardless of IF score.
    # The IF calls a 30-account loose component "anomalous" simply because it never
    # saw clusters that large during training. That is a training-distribution artifact,
    # not a fraud signal. Cap these below the 40-point flag threshold.
    n   = feats.get("cluster_size", 0)
    rvb = feats.get("refund_ratio_vs_baseline", 0.0)
    is_large_sparse = (
        n > 15
        and not feats.get("has_cycle", False)
        and feats.get("internal_txn_density", 0) < 0.03
        and rvb < 3.0
        and feats.get("reciprocal_txn_count", 0) == 0
    )
    if is_large_sparse:
        score_0_100 = min(score_0_100, 35.0)  # hard cap below flag threshold

    band = "Low"
    for threshold, label in BAND_THRESHOLDS:
        if score_0_100 >= threshold:
            band = label
            break

    return {
        "risk_score": score_0_100,
        "risk_band":  band,
        "if_score":   round(if_score_normalized, 4),
        "rule_score": round(rule_score_normalized, 4),
    }


def score_all_clusters(
    cluster_features: List[Dict[str, Any]],
    legit_cluster_ids: set,
    clf: IsolationForest = None,
    scaler: MinMaxScaler = None,
) -> List[Dict[str, Any]]:
    """Score all clusters. Trains IF if clf/scaler not provided."""
    if clf is None or scaler is None:
        legit_fvs = [
            feature_vector(f) for f in cluster_features
            if f["cluster_id"] in legit_cluster_ids
        ]
        if len(legit_fvs) == 0:
            legit_fvs = [feature_vector(f) for f in cluster_features]
        clf, scaler = train_isolation_forest(legit_fvs)

    scored = []
    for feats in cluster_features:
        scores = score_cluster(feats, clf, scaler)
        scored.append({**feats, **scores})

    return scored


def get_risk_band(score: float) -> str:
    for threshold, label in BAND_THRESHOLDS:
        if score >= threshold:
            return label
    return "Low"
