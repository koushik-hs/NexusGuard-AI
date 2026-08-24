"""
Event ingestion router — /api/events

SINGLE PIPELINE for all event types (manual and scenario-generated).

This is the only path through which payment events enter the detection system.
No demo-only shortcut exists. No alternative scoring path exists.

Ground-truth separation:
  - This router accepts PublicEvent objects (no fraud labels)
  - Scenario events arrive here after ScenarioEventMeta has been stripped
    in scenarios.py — this router never sees ground-truth labels
  - Document: see detection/event_types.py for the type boundary design

Processing pipeline per event:
  1. Validate and construct PublicEvent
  2. live_state.process_event() →
     a. Register entities (account/device/IP) if new
     b. Record transaction
     c. Rebuild affected graph subgraph
     d. Recompute cluster features
     e. Run XGBoost + IF + rule scoring
     f. Generate evidence if score >= threshold
  3. Broadcast LiveUpdate via WebSocket
  4. Return response with risk score, evidence, latency breakdown

Measured latency is REAL — no artificial delay, no timer-based staging.
"""

import uuid
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/events", tags=["events"])


# ── Request/response schemas ──────────────────────────────────────────────────

class EventSubmitRequest(BaseModel):
    """
    Request body for submitting a single payment event.
    
    No fraud labels — this is the PublicEvent type at the API boundary.
    All fields match what a real payment system would know at transaction time.
    """
    buyer_id:    str   = Field(..., description="Buyer account ID (e.g. A0001 or a new ID)")
    merchant_id: str   = Field(..., description="Merchant account ID")
    amount:      float = Field(..., gt=0, description="Transaction amount")
    txn_type:    str   = Field(default="purchase", description="purchase or refund")
    device_id:   Optional[str] = Field(default=None, description="Device fingerprint ID")
    ip_id:       Optional[str] = Field(default=None, description="IP address ID")
    timestamp:   Optional[str] = Field(default=None, description="ISO timestamp (defaults to now)")
    source:      str   = Field(default="manual", description="Event source for UI display")


class EventSubmitResponse(BaseModel):
    event_id:          str
    buyer_id:          str
    merchant_id:       str
    amount:            float
    risk_score:        float
    prev_risk_score:   float
    risk_delta:        float
    risk_band:         str
    alert_triggered:   bool
    affected_cluster_id: int
    changed_signals:   list
    evidence:          list
    latency_ms:        dict
    cluster_stats:     dict
    message:           str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/submit", response_model=EventSubmitResponse)
async def submit_event(req: EventSubmitRequest):
    """
    Submit a payment event into the real-time detection pipeline.
    
    Both manual events (from the UI simulator) and scenario-generated events
    flow through this exact endpoint. There is no alternative path.
    
    Returns the real pipeline result: risk score, evidence, latency breakdown.
    Processing time is measured and returned — it is never artificially inflated.
    """
    from realtime.state import live_state
    from detection.event_types import EventIngestBoundary
    from api.routers.websocket import broadcast

    if not live_state._initialized:
        raise HTTPException(
            status_code=503,
            detail="Live state not initialized. Pipeline may still be loading."
        )

    # Parse timestamp
    try:
        ts = datetime.fromisoformat(req.timestamp) if req.timestamp else datetime.utcnow()
    except ValueError:
        ts = datetime.utcnow()

    # ── TYPE BOUNDARY: Strip any caller-supplied labels here ──────────────────
    # EventIngestBoundary.to_public() constructs a PublicEvent with no label fields.
    # This is the documented ground-truth separation point.
    # See detection/event_types.py for the full boundary specification.
    public_event = EventIngestBoundary.to_public(
        buyer_id=req.buyer_id,
        merchant_id=req.merchant_id,
        amount=req.amount,
        timestamp=ts,
        txn_type=req.txn_type,
        is_refund=(req.txn_type == "refund"),
        device_id=req.device_id,
        ip_id=req.ip_id,
        source=req.source,
    )

    # ── Run detection pipeline ────────────────────────────────────────────────
    live_update = live_state.process_event(public_event)

    # ── Broadcast to all WebSocket clients ────────────────────────────────────
    import asyncio
    try:
        await broadcast({**live_update, "type": "live_update"})
    except Exception as e:
        # WebSocket broadcast failure should never block the API response
        print(f"[events] WebSocket broadcast failed (non-fatal): {e}")

    return EventSubmitResponse(
        event_id=public_event.event_id,
        buyer_id=public_event.buyer_id,
        merchant_id=public_event.merchant_id,
        amount=public_event.amount,
        risk_score=live_update["risk_score"],
        prev_risk_score=live_update["prev_risk_score"],
        risk_delta=live_update["risk_delta"],
        risk_band=live_update["risk_band"],
        alert_triggered=live_update["alert_triggered"],
        affected_cluster_id=live_update["affected_cluster_id"],
        changed_signals=live_update["changed_signals"],
        evidence=live_update["evidence"],
        latency_ms=live_update["latency_ms"],
        cluster_stats=live_update["cluster_stats"],
        message=(
            f"Event processed in {live_update['latency_ms']['total']:.1f}ms. "
            f"Risk: {live_update['risk_score']:.1f} ({live_update['risk_band']})"
            + (" — ALERT TRIGGERED" if live_update["alert_triggered"] else "")
        ),
    )


@router.get("/stream")
def get_event_stream(limit: int = 50):
    """Return the last N events processed by the live pipeline."""
    from realtime.state import live_state
    return {
        "events": live_state.get_event_stream(limit=min(limit, 200)),
        "total_processed": len(live_state.event_stream),
    }


@router.get("/status")
def get_live_status():
    """Return the current state of the live detection system."""
    from realtime.state import live_state
    return live_state.get_status()


@router.get("/timeline/{cluster_id}")
def get_risk_timeline(cluster_id: int):
    """Return the risk score timeline for a specific cluster."""
    from realtime.state import live_state
    timeline = live_state.get_risk_timeline(cluster_id)
    return {
        "cluster_id": cluster_id,
        "timeline": [{"timestamp": ts, "risk_score": score} for ts, score in timeline],
    }


@router.get("/rings")
def get_live_rings():
    """Return all currently flagged rings from the live detection state."""
    from realtime.state import live_state
    rings = live_state.get_flagged_rings()
    return {
        "rings": sorted(rings, key=lambda r: r.get("risk_score", 0), reverse=True),
        "count": len(rings),
    }
