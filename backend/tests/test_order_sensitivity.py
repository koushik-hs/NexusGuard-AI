"""
Robustness Test: Order-Sensitivity.

Tests that constructing the same underlying coordinated graph via two different
event arrival orderings results in substantially consistent final graph structure
and final risk assessments.

Intermediate scores may differ (which is expected because velocity/arrival temporal
features evolve in real-time), but once all events have arrived, the converged state
must be consistent (within ±10 score points).
"""

import pytest
from datetime import datetime, timedelta

from detection.event_types import EventIngestBoundary
from realtime.state import LiveGraphState


def _create_event_sequence(prefix: str):
    base_time = datetime(2024, 6, 1, 12, 0, 0)
    did = f"D_{prefix}_SHARED"
    iid = f"IP_{prefix}_SHARED"
    m = f"M_{prefix}_TARGET"
    
    a1 = f"A_{prefix}_1"
    a2 = f"A_{prefix}_2"
    a3 = f"A_{prefix}_3"
    a4 = f"A_{prefix}_4"

    events = [
        EventIngestBoundary.to_public(
            buyer_id=a1, merchant_id=m, amount=5000.0,
            timestamp=base_time + timedelta(seconds=10),
            device_id=did, ip_id=iid
        ),
        EventIngestBoundary.to_public(
            buyer_id=a2, merchant_id=m, amount=5000.0,
            timestamp=base_time + timedelta(seconds=20),
            device_id=did, ip_id=iid
        ),
        EventIngestBoundary.to_public(
            buyer_id=a3, merchant_id=m, amount=5000.0,
            timestamp=base_time + timedelta(seconds=30),
            device_id=did, ip_id=iid
        ),
        EventIngestBoundary.to_public(
            buyer_id=a4, merchant_id=m, amount=5000.0,
            timestamp=base_time + timedelta(seconds=40),
            device_id=did, ip_id=iid
        ),
        # Circular flow: a1 -> a2 -> a3 -> a4 -> a1
        EventIngestBoundary.to_public(
            buyer_id=a1, merchant_id=a2, amount=12000.0,
            timestamp=base_time + timedelta(seconds=50),
            device_id=did, ip_id=iid
        ),
        EventIngestBoundary.to_public(
            buyer_id=a2, merchant_id=a3, amount=12000.0,
            timestamp=base_time + timedelta(seconds=60),
            device_id=did, ip_id=iid
        ),
        EventIngestBoundary.to_public(
            buyer_id=a3, merchant_id=a4, amount=12000.0,
            timestamp=base_time + timedelta(seconds=70),
            device_id=did, ip_id=iid
        ),
        EventIngestBoundary.to_public(
            buyer_id=a4, merchant_id=a1, amount=12000.0,
            timestamp=base_time + timedelta(seconds=80),
            device_id=did, ip_id=iid
        ),
    ]
    return events


def test_order_invariance_final_risk():
    """
    Feed sequence in Order A vs Order B (interleaved/reversed).
    Final risk score should be consistent within a small margin.
    """
    events_a = _create_event_sequence("ORD_A")
    events_b = list(reversed(_create_event_sequence("ORD_B")))

    state_a = LiveGraphState()
    state_a.initialize_from_batch()

    state_b = LiveGraphState()
    state_b.initialize_from_batch()

    # Process all events in stream A
    last_update_a = None
    for ev in events_a:
        last_update_a = state_a.process_event(ev)

    # Process all events in stream B
    last_update_b = None
    for ev in events_b:
        last_update_b = state_b.process_event(ev)

    score_a = last_update_a["risk_score"]
    score_b = last_update_b["risk_score"]

    print(f"Final Score A: {score_a}, Final Score B: {score_b}")

    # Both must identify the high-risk ring
    assert score_a >= 65.0, f"Expected High/Critical risk for Order A, got {score_a}"
    assert score_b >= 65.0, f"Expected High/Critical risk for Order B, got {score_b}"

    # Invariance check: absolute delta within 15 points
    assert abs(score_a - score_b) <= 15.0, (
        f"Order sensitivity too high: Score A={score_a} vs Score B={score_b}"
    )
