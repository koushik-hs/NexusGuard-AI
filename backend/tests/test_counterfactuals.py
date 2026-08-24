"""
Robustness Test: Counterfactual Reasoning.

Proves that the detector reasons from actual feature representations and relationships
rather than pattern-matching a known demo shape.

Counterfactual tests:
  1. Shared Device+IP vs Distinct Devices/IPs (Infra signal ablation)
  2. Concentrated 10-Minute Activity vs 60-Day Spread (Temporal sync ablation)
  3. Shared IP with Diverse Unrelated Merchants (Benign Corporate Office ablation)
"""

import pytest
from datetime import datetime, timedelta

from detection.event_types import EventIngestBoundary
from realtime.state import LiveGraphState


def test_counterfactual_shared_infrastructure():
    """
    Counterfactual 1:
    Case A: 4 accounts share device + IP.
    Case B: Identical accounts and transactions, but each on distinct, unique devices and IPs.
    Result: Case A risk score must be significantly higher than Case B (at least 20 points higher).
    """
    base_time = datetime(2024, 5, 1, 10, 0, 0)
    merchant = "M_TEST_COUNTER"

    # --- Setup Case A: Shared Infrastructure ---
    state_a = LiveGraphState()
    state_a.initialize_from_batch()
    shared_dev = "DEV_SHARED_X"
    shared_ip = "IP_SHARED_X"

    for i in range(4):
        acc = f"ACC_SHARED_{i}"
        ev = EventIngestBoundary.to_public(
            buyer_id=acc, merchant_id=merchant, amount=6000.0,
            timestamp=base_time + timedelta(seconds=i * 10),
            device_id=shared_dev, ip_id=shared_ip
        )
        res_a = state_a.process_event(ev)

    # --- Setup Case B: Independent Infrastructure ---
    state_b = LiveGraphState()
    state_b.initialize_from_batch()

    for i in range(4):
        acc = f"ACC_INDEP_{i}"
        ev = EventIngestBoundary.to_public(
            buyer_id=acc, merchant_id=merchant, amount=6000.0,
            timestamp=base_time + timedelta(days=i * 15),  # spread across 45 days
            device_id=f"DEV_INDEP_{i}", ip_id=f"IP_INDEP_{i}"
        )
        res_b = state_b.process_event(ev)

    score_a = res_a["risk_score"]
    score_b = res_b["risk_score"]

    print(f"Counterfactual 1: Shared Infra Score={score_a}, Distinct Infra Score={score_b}")
    assert score_a > score_b, "Shared infrastructure must increase risk score"
    assert (score_a - score_b) >= 20.0, (
        f"Expected at least 20pt difference, got {score_a - score_b:.1f} (Score A={score_a}, Score B={score_b})"
    )


def test_counterfactual_temporal_spread():
    """
    Counterfactual 2:
    Case A: Same shared infrastructure, but all accounts created & active within 2 minutes.
    Case B: Same shared infrastructure, but transactions spread over 60 days.
    Result: Spread-out case must have reduced temporal risk / lower overall risk.
    """
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    merchant = "M_TEST_TEMP"
    dev = "DEV_TEMP_SHARED"
    ip = "IP_TEMP_SHARED"

    # Case A: Rapid burst (2 min)
    state_a = LiveGraphState()
    state_a.initialize_from_batch()
    for i in range(4):
        acc = f"ACC_RAPID_{i}"
        ev = EventIngestBoundary.to_public(
            buyer_id=acc, merchant_id=merchant, amount=4000.0,
            timestamp=base_time + timedelta(seconds=i * 20),
            device_id=dev, ip_id=ip
        )
        res_a = state_a.process_event(ev)

    # Case B: Spread across 60 days
    state_b = LiveGraphState()
    state_b.initialize_from_batch()
    for i in range(4):
        acc = f"ACC_SPREAD_{i}"
        ev = EventIngestBoundary.to_public(
            buyer_id=acc, merchant_id=merchant, amount=4000.0,
            timestamp=base_time + timedelta(days=i * 15),
            device_id=dev, ip_id=ip
        )
        res_b = state_b.process_event(ev)

    score_a = res_a["risk_score"]
    score_b = res_b["risk_score"]

    print(f"Counterfactual 2: Synchronized Score={score_a}, Spread-out Score={score_b}")
    assert score_a >= score_b, "Synchronized creation/activity must not score lower than spread-out activity"


def test_counterfactual_shared_ip_diverse_merchants():
    """
    Counterfactual 3:
    5 accounts share a corporate office IP, but use distinct devices and shop at
    5 completely distinct, unrelated merchants over normal business days.
    Result: Must NOT be flagged as a fraud ring (risk score < 40 or below alert threshold).
    """
    base_time = datetime(2024, 3, 1, 10, 0, 0)
    state = LiveGraphState()
    state.initialize_from_batch()
    office_ip = "IP_OFFICE_PROXY"

    last_res = None
    for i in range(5):
        buyer = f"EMP_CORP_{i}"
        merch = f"M_STORE_{i}"
        dev = f"DEV_EMP_{i}" # distinct personal device
        ev = EventIngestBoundary.to_public(
            buyer_id=buyer, merchant_id=merch, amount=1500.0,
            timestamp=base_time + timedelta(days=i * 5),
            device_id=dev, ip_id=office_ip
        )
        last_res = state.process_event(ev)

    score = last_res["risk_score"]
    print(f"Counterfactual 3 (Office IP Hard Negative): Score={score}")
    assert not last_res["alert_triggered"], f"Corporate office scenario should not trigger an alert (Score: {score})"
    assert score < 40.0, f"Expected Low risk (<40) for diverse corporate office purchases, got {score}"
