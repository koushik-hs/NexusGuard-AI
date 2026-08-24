"""
Hybrid risk scorer — v3.

Model stack:
  1. Isolation Forest (IF)         — anomaly signal (unsupervised)
  2. XGBoost                       — primary supervised model (if trained)
  3. Rule-based structural signal  — deterministic, interpretable

Hybrid formula (when XGBoost is available):
  score = 0.35 × IF_normalized + 0.40 × XGB_probability + 0.25 × rule_score
  → XGBoost is primary; IF catches novel anomalies; rules ensure interpretability floor

Fallback (when XGBoost is not available):
  score = 0.40 × IF_normalized + 0.60 × rule_score
  → Backward-compatible with v2 behavior

Risk bands (heuristic defaults — stated plainly, not data-derived):
  Low      0–39
  Medium   40–64
  High     65–84
  Critical 85–100

Decision log entry: XGBoost was chosen over a single IF model because it is a
supervised discriminative classifier that can learn non-linear feature
combinations. IF is kept as a complementary anomaly signal because it detects
novel patterns that might not match training ring templates. Rules are kept at
25% weight to ensure the score remains partially interpretable — a judge can
always trace ≥25% of the score back to deterministic structural signals.
"""

import os
import pickle
from typing import Dict, List, Any, Tuple, Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

from detection.feature_extractor import feature_vector

MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
IF_PATH    = os.path.join(MODEL_DIR, "if_model.pkl")
XGB_PATH   = os.path.join(MODEL_DIR, "xgb_model.pkl")

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
    DAYS_1_S   = 1 * 86400
    is_benign_spread = (
        spread != float("inf")
        and spread > DAYS_1_S
        and n <= 8
        and not feats["has_cycle"]
        and rvb < 3.0
    )
    infra_scale = 0.25 if is_benign_spread else 1.0

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
    if multi >= 3 and not is_benign_spread:
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
    with open(IF_PATH, "wb") as f:
        pickle.dump({"model": clf, "scaler": scaler}, f)

    print(f"[scorer] IsolationForest trained on {len(X)} legitimate clusters. "
          f"Model saved to {IF_PATH}")
    return clf, scaler


def load_isolation_forest() -> Tuple[IsolationForest, MinMaxScaler]:
    with open(IF_PATH, "rb") as f:
        data = pickle.load(f)
    return data["model"], data["scaler"]


def load_xgboost() -> Optional[Any]:
    """Load XGBoost model if available. Returns None if not trained yet."""
    if not os.path.exists(XGB_PATH):
        return None
    try:
        with open(XGB_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"[scorer] Warning: could not load XGBoost model: {e}")
        return None


def score_cluster(
    feats: Dict[str, Any],
    clf: IsolationForest,
    scaler: MinMaxScaler,
    clf_xgb=None,
) -> Dict[str, Any]:
    """
    Compute the hybrid risk score for one cluster.
    
    Uses 3-model hybrid if XGBoost is available:
      0.35 × IF_normalized + 0.40 × XGB_probability + 0.25 × rule_score
    Falls back to 2-model hybrid if XGBoost is not available:
      0.40 × IF_normalized + 0.60 × rule_score
    """
    fv  = np.array(feature_vector(feats)).reshape(1, -1)

    raw_if               = clf.score_samples(fv)[0]
    if_score_normalized  = float(1.0 - scaler.transform([[raw_if]])[0][0])
    if_score_normalized  = max(0.0, min(1.0, if_score_normalized))

    rule_score_normalized = _rule_score(feats)

    if clf_xgb is not None:
        try:
            xgb_prob = float(clf_xgb.predict_proba(fv)[0][1])
            combined = 0.35 * if_score_normalized + 0.40 * xgb_prob + 0.25 * rule_score_normalized
            model_used = "3-model (IF+XGB+rules)"
        except Exception as e:
            print(f"[scorer] XGBoost inference failed ({e}); falling back to IF+rules.")
            xgb_prob = None
            combined = 0.40 * if_score_normalized + 0.60 * rule_score_normalized
            model_used = "2-model fallback (IF+rules)"
    else:
        xgb_prob = None
        combined = 0.40 * if_score_normalized + 0.60 * rule_score_normalized
        model_used = "2-model (IF+rules)"

    score_0_100 = round(combined * 100, 1)

    # Hard cap: large sparse components cannot be flagged regardless of IF/XGB score.
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
        score_0_100 = min(score_0_100, 35.0)

    band = "Low"
    for threshold, label in BAND_THRESHOLDS:
        if score_0_100 >= threshold:
            band = label
            break

    result = {
        "risk_score": score_0_100,
        "risk_band":  band,
        "if_score":   round(if_score_normalized, 4),
        "rule_score": round(rule_score_normalized, 4),
        "model_used": model_used,
    }
    if xgb_prob is not None:
        result["xgb_score"] = round(xgb_prob, 4)

    return result


def score_all_clusters(
    cluster_features: List[Dict[str, Any]],
    legit_cluster_ids: set,
    clf: IsolationForest = None,
    scaler: MinMaxScaler = None,
    clf_xgb=None,
) -> List[Dict[str, Any]]:
    """Score all clusters. Trains IF if clf/scaler not provided. Loads XGBoost if not given."""
    if clf is None or scaler is None:
        legit_fvs = [
            feature_vector(f) for f in cluster_features
            if f["cluster_id"] in legit_cluster_ids
        ]
        if len(legit_fvs) == 0:
            legit_fvs = [feature_vector(f) for f in cluster_features]
        clf, scaler = train_isolation_forest(legit_fvs)

    if clf_xgb is None:
        clf_xgb = load_xgboost()
        if clf_xgb is not None:
            print("[scorer] XGBoost model loaded — using 3-model hybrid scoring.")
        else:
            print("[scorer] XGBoost model not found — using IF+rules fallback.")

    scored = []
    for feats in cluster_features:
        scores = score_cluster(feats, clf, scaler, clf_xgb)
        scored.append({**feats, **scores})

    return scored


def get_risk_band(score: float) -> str:
    for threshold, label in BAND_THRESHOLDS:
        if score >= threshold:
            return label
    return "Low"
