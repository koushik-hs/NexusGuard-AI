"""Metrics router — /api/metrics endpoints."""

import json
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "data")
EVAL_PATH = os.path.join(DATA_DIR, "evaluation_results.json")

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _load_eval():
    if not os.path.exists(EVAL_PATH):
        raise HTTPException(status_code=503,
                            detail="Evaluation has not run yet.")
    with open(EVAL_PATH) as f:
        return json.load(f)


@router.get("")
def get_metrics() -> Dict[str, Any]:
    """Full evaluation results including all baselines."""
    return _load_eval()


@router.get("/baselines")
def get_baselines() -> Dict[str, Any]:
    """4-baseline comparison table for the frontend metrics screen."""
    data = _load_eval()
    return data.get("baselines_comparison", {
        "baseline_1_txn_only":   data.get("transaction_only_baseline", {}),
        "final_hybrid":          data.get("graph_aware_detector", {}),
    })


@router.get("/ablation")
def get_ablation() -> Dict[str, Any]:
    """Feature ablation results (requires ml/feature_ablation.py to have run)."""
    path = os.path.join(DATA_DIR, "ablation_results.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404,
                            detail="Ablation results not found. Run: python -m ml.feature_ablation")
    with open(path) as f:
        return json.load(f)


@router.get("/ring-level")
def get_ring_level() -> Dict[str, Any]:
    """Ring-level detection rates by ring type."""
    return _load_eval().get("ring_level", {})


@router.get("/benign-overlap")
def get_benign_overlap() -> Dict[str, Any]:
    """FP rate on benign overlap cases, by benign type."""
    return _load_eval().get("benign_overlap_analysis", {})
