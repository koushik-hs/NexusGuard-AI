"""
FastAPI application entry point — v2.

On startup, checks if detection pipeline outputs exist.
If not, runs the full pipeline automatically.

New endpoints:
  POST /api/pipeline/run  — trigger fresh data gen + detection + evaluation
  GET  /api/metrics/baselines — 4-baseline comparison table
  GET  /api/metrics/ablation  — feature ablation results
  GET  /api/rings/hero        — hero demo ring
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import rings, metrics

DATA_DIR       = os.path.join(os.path.dirname(__file__), "..", "data")
RINGS_PATH     = os.path.join(DATA_DIR, "rings.json")
EVAL_PATH      = os.path.join(DATA_DIR, "evaluation_results.json")
ACCOUNTS_PATH  = os.path.join(DATA_DIR, "accounts.csv")


def _run_pipeline_if_needed():
    """Auto-run data gen + detection + evaluation if outputs don't exist."""
    if not os.path.exists(ACCOUNTS_PATH):
        print("[startup] No data found. Running synthetic data generator...")
        from data_gen.generator import generate
        generate()

    if not os.path.exists(RINGS_PATH):
        print("[startup] No rings.json found. Running detection pipeline...")
        from detection.pipeline import run_pipeline
        run_pipeline()

    if not os.path.exists(EVAL_PATH):
        print("[startup] No evaluation_results.json found. Running evaluator...")
        from evaluation.evaluator import evaluate
        evaluate()

    print("[startup] [OK] All pipeline outputs ready.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_pipeline_if_needed()
    yield


app = FastAPI(
    title="Coordinated Payment Abuse Detection API",
    description=(
        "Graph-based detection of coordinated fraud rings on payment platforms. "
        "Built for Razorpay AI Buildathon — Track 02: AI Risk Manager."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000",
                   "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(rings.router)
app.include_router(metrics.router)


@app.get("/")
def root():
    return {
        "name": "Coordinated Payment Abuse Detection API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": [
            "GET  /api/rings",
            "GET  /api/rings/hero",
            "GET  /api/rings/{id}",
            "GET  /api/rings/{id}/graph",
            "POST /api/rings/{id}/investigate",
            "GET  /api/metrics",
            "GET  /api/metrics/baselines",
            "GET  /api/metrics/ablation",
            "POST /api/pipeline/run",
        ],
    }


@app.get("/health")
def health():
    rings_ready = os.path.exists(RINGS_PATH)
    eval_ready  = os.path.exists(EVAL_PATH)
    return {
        "status":            "ok" if (rings_ready and eval_ready) else "initializing",
        "rings_ready":       rings_ready,
        "evaluation_ready":  eval_ready,
    }


@app.post("/api/pipeline/run")
def run_full_pipeline():
    """
    Trigger a fresh data generation + detection + evaluation cycle.
    WARNING: This deletes existing data and regenerates from scratch.
    Takes 30–120 seconds depending on hardware.
    """
    import shutil
    # Clear old data so pipeline re-runs fully
    for fname in ["accounts.csv", "transactions.csv", "rings.json",
                  "all_clusters.json", "evaluation_results.json",
                  "labels.csv", "if_model.pkl", "hero_accounts.json"]:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            os.remove(fpath)

    from data_gen.generator import generate
    from detection.pipeline import run_pipeline
    from evaluation.evaluator import evaluate

    generate()
    run_pipeline()
    results = evaluate()

    return {"status": "ok", "summary": results.get("data_summary", {})}
