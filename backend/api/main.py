"""
FastAPI application entry point — v3.

Real-Time & Batch Hybrid Pipeline:
  - Batch Fallback: full dataset generation, model training, graph clustering, evidence persist
  - Real-Time Layer: live graph state, WebSocket streaming, single-pipeline event ingestion, scenario simulation

Endpoints:
  GET  /api/rings                  — list detected rings
  GET  /api/rings/hero             — hero demo ring
  GET  /api/rings/{id}             — ring details
  GET  /api/rings/{id}/graph       — ring subgraph
  POST /api/rings/{id}/investigate — GenAI investigation report
  GET  /api/metrics                — full evaluation results
  GET  /api/metrics/baselines      — 5-baseline comparison table
  GET  /api/metrics/ablation       — feature ablation results
  POST /api/events/submit          — real-time payment event ingestion
  GET  /api/events/stream          — live event stream log
  GET  /api/events/status          — live graph engine status
  GET  /api/events/timeline/{id}   — risk evolution timeline
  GET  /api/scenarios/list         — list available scenario simulations
  POST /api/scenarios/run          — run live payment scenario stream
  WS   /api/ws                     — live WebSocket feed
  POST /api/pipeline/run           — trigger fresh batch pipeline
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import rings, metrics, events, scenarios, websocket
from realtime.state import live_state

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

    print("[startup] [OK] All batch pipeline outputs ready.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_pipeline_if_needed()
    # Initialize live in-memory state from batch data
    live_state.initialize_from_batch()
    yield


app = FastAPI(
    title="NexusGuard AI — Coordinated Payment Abuse Detection",
    description=(
        "Real-time graph-aware detection and investigation of coordinated fraud rings on payment platforms. "
        "Built for Razorpay AI Buildathon — Track 02: AI Risk Manager."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(rings.router)
app.include_router(metrics.router)
app.include_router(events.router)
app.include_router(scenarios.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    return {
        "name": "NexusGuard AI — Real-Time Coordinated Payment Abuse Detection API",
        "version": "3.0.0",
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
            "POST /api/events/submit",
            "GET  /api/events/stream",
            "GET  /api/events/status",
            "GET  /api/events/timeline/{id}",
            "GET  /api/scenarios/list",
            "POST /api/scenarios/run",
            "WS   /api/ws",
            "POST /api/pipeline/run",
        ],
    }


@app.get("/health")
def health():
    rings_ready = os.path.exists(RINGS_PATH)
    eval_ready  = os.path.exists(EVAL_PATH)
    live_status = live_state.get_status()
    return {
        "status":            "ok" if (rings_ready and eval_ready and live_status["initialized"]) else "initializing",
        "rings_ready":       rings_ready,
        "evaluation_ready":  eval_ready,
        "live_engine":       live_status,
    }


@app.post("/api/pipeline/run")
def run_full_pipeline():
    """
    Trigger a fresh data generation + detection + evaluation cycle.
    WARNING: This deletes existing data and regenerates from scratch.
    """
    # Clear old data so pipeline re-runs fully
    for fname in ["accounts.csv", "transactions.csv", "rings.json",
                  "all_clusters.json", "evaluation_results.json",
                  "labels.csv", "if_model.pkl", "xgb_model.pkl", "rf_model.pkl", "hero_accounts.json"]:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            os.remove(fpath)

    from data_gen.generator import generate
    from ml.train import train_and_evaluate
    from detection.pipeline import run_pipeline
    from evaluation.evaluator import evaluate

    generate()
    train_and_evaluate()
    run_pipeline()
    results = evaluate()
    live_state.initialize_from_batch()

    return {"status": "ok", "summary": results.get("data_summary", {})}
