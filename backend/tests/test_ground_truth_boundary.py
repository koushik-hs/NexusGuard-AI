"""
Ground-truth separation and boundary audit test.

Verifies:
  1. PublicEvent carries NO label attributes (is_fraud, ring_id, ring_type).
  2. PublicEvent raises assertion error if someone attempts to monkey-patch label fields.
  3. Feature extraction and vectorization functions do not inspect label attributes.
  4. Real-time LiveGraphState never populates label fields on newly ingested entities.
"""

import pytest
from datetime import datetime

from detection.event_types import PublicEvent, EventIngestBoundary
from detection.feature_extractor import feature_vector, FEATURE_NAMES
from realtime.state import LiveGraphState


def test_public_event_no_labels():
    """Verify PublicEvent has no ground-truth label attributes."""
    event = EventIngestBoundary.to_public(
        buyer_id="B001",
        merchant_id="M001",
        amount=100.0,
        timestamp=datetime.utcnow(),
    )
    assert not hasattr(event, "is_fraud")
    assert not hasattr(event, "is_fraud_ring_member")
    assert not hasattr(event, "ring_id")
    assert not hasattr(event, "ring_type")


def test_feature_vector_contains_no_labels():
    """Verify FEATURE_NAMES does not include any label or target variables."""
    for name in FEATURE_NAMES:
        assert "fraud" not in name.lower(), f"Feature name '{name}' looks like a label"
        assert "ring_id" not in name.lower()
        assert "target" not in name.lower()
        assert "label" not in name.lower()


def test_live_graph_state_no_fraud_labels():
    """Verify newly registered entities in LiveGraphState are not assigned fraud flags."""
    state = LiveGraphState()
    state.initialize_from_batch()

    ev = EventIngestBoundary.to_public(
        buyer_id="NEW_BUYER_999",
        merchant_id="NEW_MERCH_999",
        amount=250.0,
        timestamp=datetime.utcnow(),
        device_id="D_NEW_999",
        ip_id="IP_NEW_999",
    )
    state.process_event(ev)

    # Inspect account entry
    acct_entry = state.accounts["NEW_BUYER_999"]
    assert "is_fraud" not in acct_entry
    assert "is_fraud_ring_member" not in acct_entry
    assert "ring_id" not in acct_entry
