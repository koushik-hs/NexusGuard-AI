"""
Scenario simulator router — /api/scenarios

Simulates realistic payment event streams for live demonstrations.

STRICT PRINCIPLE:
  "Simulate the payments. Do not simulate the detection."
  The scenarios in this module ONLY generate sequences of ordinary synthetic
  events with realistic amounts, timestamps, device IDs, IP IDs, and accounts.
  
  They NEVER:
    - Directly create an alert
    - Directly assign a risk score
    - Construct a fraud-ring object
    - Tell the detector "this is fraud"

All events pass through `live_state.process_event()` or `POST /api/events/submit`
as `PublicEvent` objects with no label fields.

Available Scenarios:
  1. coordinated_ring          — Synchronized creation, shared device/IP, circular flow (Hero pattern)
  2. shared_device_ring        — Rapid burst of accounts on one device transacting with target merchant
  3. refund_farming            — Collusion with repeated high-refund volume
  4. circular_flow             — Closed-loop transfers A → B → C → D → A
  5. coordinated_creation      — Burst of accounts created in seconds before normal transactions
  6. legit_family_business     — Hard negative: merchants sharing device + IP, benign spread, normal refund
  7. legit_corporate_office    — Hard negative: office network IP with many buyers purchasing from diverse merchants
  8. legit_high_volume         — Hard negative: popular store with high velocity, diverse buyers
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from detection.event_types import EventIngestBoundary, ScenarioEventMeta
from realtime.state import live_state
from api.routers.websocket import broadcast

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class ScenarioRunRequest(BaseModel):
    scenario_type: str = Field(..., description="Type of scenario to run")
    inter_event_delay_ms: int = Field(default=300, ge=0, le=2000, description="Delay between events in ms for live stream visualization")
    custom_name: Optional[str] = Field(default=None, description="Optional custom name or tag")


class ScenarioRunResponse(BaseModel):
    scenario_id: str
    scenario_type: str
    status: str
    total_events: int
    accounts_involved: List[str]
    description: str
    is_hard_negative: bool


# ── Scenario Event Generators ────────────────────────────────────────────────

def _gen_coordinated_ring(base_time: datetime) -> Tuple[List[Dict[str, Any]], ScenarioEventMeta, str]:
    """Hero-style coordinated fraud ring."""
    scenario_id = f"scen_coord_{uuid.uuid4().hex[:6]}"
    did = live_state.generate_new_device_id()
    iid = live_state.generate_new_ip_id()
    
    # 5 accounts created in rapid succession
    accounts = [live_state.generate_new_account_id() for _ in range(5)]
    target_merchant = live_state.generate_new_account_id()
    
    events = []
    # 1. Circular flow between ring members
    base_amount = 28000.0
    for i in range(len(accounts)):
        buyer = accounts[i]
        merchant = accounts[(i + 1) % len(accounts)]
        amt = round(base_amount * random.uniform(0.98, 1.02), 2)
        events.append({
            "buyer_id": buyer,
            "merchant_id": merchant,
            "amount": amt,
            "timestamp": base_time + timedelta(seconds=i * 2),
            "txn_type": "purchase",
            "device_id": did,
            "ip_id": iid,
            "source": "scenario:coordinated_ring",
        })

    # 2. Funneled high-value transactions with elevated refunds to target merchant
    for j, acc in enumerate(accounts):
        for k in range(2):
            is_ref = (k == 1)
            events.append({
                "buyer_id": acc,
                "merchant_id": target_merchant,
                "amount": round(random.uniform(4000, 15000), 2),
                "timestamp": base_time + timedelta(seconds=20 + (j * 2 + k) * 3),
                "txn_type": "refund" if is_ref else "purchase",
                "device_id": did,
                "ip_id": iid,
                "source": "scenario:coordinated_ring",
            })

    meta = ScenarioEventMeta(
        event_id=scenario_id,
        scenario_id=scenario_id,
        scenario_type="CoordinatedRing",
        is_fraud=True,
        ring_id="SYN_COORD",
    )
    desc = "5 synchronized accounts sharing Device & IP, executing circular flow and elevated refund farming."
    return events, meta, desc


def _gen_shared_device_ring(base_time: datetime) -> Tuple[List[Dict[str, Any]], ScenarioEventMeta, str]:
    """Rapid succession of accounts sharing one device."""
    scenario_id = f"scen_sdev_{uuid.uuid4().hex[:6]}"
    did = live_state.generate_new_device_id()
    accounts = [live_state.generate_new_account_id() for _ in range(4)]
    merchant = live_state.generate_new_account_id()

    events = []
    for i, acc in enumerate(accounts):
        iid = live_state.generate_new_ip_id() # distinct IP per account
        for j in range(3):
            events.append({
                "buyer_id": acc,
                "merchant_id": merchant,
                "amount": round(random.uniform(1500, 6000), 2),
                "timestamp": base_time + timedelta(seconds=i * 5 + j * 2),
                "txn_type": "purchase",
                "device_id": did,
                "ip_id": iid,
                "source": "scenario:shared_device_ring",
            })

    meta = ScenarioEventMeta(
        event_id=scenario_id,
        scenario_id=scenario_id,
        scenario_type="SharedDeviceRing",
        is_fraud=True,
        ring_id="SYN_SDEV",
    )
    desc = "4 separate buyer accounts all operating from the exact same hardware device ID targeting one merchant."
    return events, meta, desc


def _gen_refund_farming(base_time: datetime) -> Tuple[List[Dict[str, Any]], ScenarioEventMeta, str]:
    """Collusive buyer-merchant pair generating high refund ratios."""
    scenario_id = f"scen_ref_{uuid.uuid4().hex[:6]}"
    did = live_state.generate_new_device_id()
    iid = live_state.generate_new_ip_id()
    buyers = [live_state.generate_new_account_id() for _ in range(3)]
    merchant = live_state.generate_new_account_id()

    events = []
    t = 0
    for b in buyers:
        for _ in range(4):
            amt = round(random.uniform(3000, 12000), 2)
            # Purchase
            events.append({
                "buyer_id": b,
                "merchant_id": merchant,
                "amount": amt,
                "timestamp": base_time + timedelta(seconds=t),
                "txn_type": "purchase",
                "device_id": did,
                "ip_id": iid,
                "source": "scenario:refund_farming",
            })
            t += 2
            # High refund probability (60%)
            if random.random() < 0.60:
                events.append({
                    "buyer_id": b,
                    "merchant_id": merchant,
                    "amount": amt,
                    "timestamp": base_time + timedelta(seconds=t),
                    "txn_type": "refund",
                    "device_id": did,
                    "ip_id": iid,
                    "source": "scenario:refund_farming",
                })
                t += 2

    meta = ScenarioEventMeta(
        event_id=scenario_id,
        scenario_id=scenario_id,
        scenario_type="RefundFarming",
        is_fraud=True,
        ring_id="SYN_REFUND",
    )
    desc = "Coordinated buyer-merchant collusion with 60%+ refund rate on shared infrastructure."
    return events, meta, desc


def _gen_circular_flow(base_time: datetime) -> Tuple[List[Dict[str, Any]], ScenarioEventMeta, str]:
    """Pure circular money flow A -> B -> C -> D -> A."""
    scenario_id = f"scen_circ_{uuid.uuid4().hex[:6]}"
    accounts = [live_state.generate_new_account_id() for _ in range(4)]
    did = live_state.generate_new_device_id()
    iid = live_state.generate_new_ip_id()

    events = []
    base_amt = 45000.0
    for i in range(len(accounts)):
        b = accounts[i]
        m = accounts[(i + 1) % len(accounts)]
        events.append({
            "buyer_id": b,
            "merchant_id": m,
            "amount": round(base_amt * random.uniform(0.99, 1.01), 2),
            "timestamp": base_time + timedelta(seconds=i * 3),
            "txn_type": "purchase",
            "device_id": did,
            "ip_id": iid,
            "source": "scenario:circular_flow",
        })

    meta = ScenarioEventMeta(
        event_id=scenario_id,
        scenario_id=scenario_id,
        scenario_type="CircularFlow",
        is_fraud=True,
        ring_id="SYN_CIRC",
    )
    desc = "Structured round-trip money transfer chain (A→B→C→D→A) with matched high-value amounts."
    return events, meta, desc


def _gen_legit_family_business(base_time: datetime) -> Tuple[List[Dict[str, Any]], ScenarioEventMeta, str]:
    """HARD NEGATIVE: Family business sharing a device + IP, but legitimate activity."""
    scenario_id = f"scen_fam_{uuid.uuid4().hex[:6]}"
    did = live_state.generate_new_device_id()
    iid = live_state.generate_new_ip_id()
    # 2 family merchants
    merchants = [live_state.generate_new_account_id() for _ in range(2)]
    # Diverse independent buyers
    buyers = [live_state.generate_new_account_id() for _ in range(6)]

    events = []
    for i, b in enumerate(buyers):
        m = random.choice(merchants)
        b_dev = live_state.generate_new_device_id()
        b_ip = live_state.generate_new_ip_id()
        events.append({
            "buyer_id": b,
            "merchant_id": m,
            "amount": round(random.uniform(300, 2500), 2),
            "timestamp": base_time + timedelta(minutes=i * 15), # Spread out over hours/days
            "txn_type": "purchase",
            "device_id": b_dev,
            "ip_id": b_ip,
            "source": "scenario:legit_family_business",
        })

    meta = ScenarioEventMeta(
        event_id=scenario_id,
        scenario_id=scenario_id,
        scenario_type="LegitFamilyBusiness",
        is_fraud=False, # Hard Negative
    )
    desc = "HARD NEGATIVE: Family retail business with shared store device/IP receiving spread-out purchases from diverse buyers."
    return events, meta, desc


def _gen_legit_corporate_office(base_time: datetime) -> Tuple[List[Dict[str, Any]], ScenarioEventMeta, str]:
    """HARD NEGATIVE: Corporate office network with many employees purchasing online."""
    scenario_id = f"scen_corp_{uuid.uuid4().hex[:6]}"
    office_ip = live_state.generate_new_ip_id()
    employees = [live_state.generate_new_account_id() for _ in range(5)]
    merchants = [live_state.generate_new_account_id() for _ in range(4)]

    events = []
    for i, emp in enumerate(employees):
        emp_dev = live_state.generate_new_device_id() # Each employee has own laptop/phone
        m = random.choice(merchants)
        events.append({
            "buyer_id": emp,
            "merchant_id": m,
            "amount": round(random.uniform(200, 1800), 2),
            "timestamp": base_time + timedelta(minutes=i * 20),
            "txn_type": "purchase",
            "device_id": emp_dev,
            "ip_id": office_ip,
            "source": "scenario:legit_corporate_office",
        })

    meta = ScenarioEventMeta(
        event_id=scenario_id,
        scenario_id=scenario_id,
        scenario_type="LegitCorporateOffice",
        is_fraud=False, # Hard Negative
    )
    desc = "HARD NEGATIVE: Office network where 5 employees share an outbound IP, but use distinct devices to shop at unrelated stores."
    return events, meta, desc


SCENARIO_GENERATORS = {
    "coordinated_ring":       (_gen_coordinated_ring, False),
    "shared_device_ring":     (_gen_shared_device_ring, False),
    "refund_farming":         (_gen_refund_farming, False),
    "circular_flow":          (_gen_circular_flow, False),
    "legit_family_business":  (_gen_legit_family_business, True),
    "legit_corporate_office": (_gen_legit_corporate_office, True),
}


# ── Execution background worker ──────────────────────────────────────────────

async def _stream_scenario_events(events: List[Dict[str, Any]], delay_ms: int):
    """Feed events one by one through the official pipeline with delay for live visual impact."""
    for raw in events:
        # Convert to PublicEvent via boundary
        pub = EventIngestBoundary.to_public(
            buyer_id=raw["buyer_id"],
            merchant_id=raw["merchant_id"],
            amount=raw["amount"],
            timestamp=raw["timestamp"],
            txn_type=raw.get("txn_type", "purchase"),
            is_refund=(raw.get("txn_type") == "refund"),
            device_id=raw.get("device_id"),
            ip_id=raw.get("ip_id"),
            source=raw.get("source", "scenario"),
        )
        # Process in real-time engine
        update = live_state.process_event(pub)
        
        # Broadcast to WebSocket
        try:
            await broadcast({**update, "type": "live_update"})
        except Exception:
            pass

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/list")
def list_scenarios():
    """List all available scenario simulations for the dashboard."""
    return [
        {
            "id": "coordinated_ring",
            "name": "Coordinated Fraud Ring (Hero)",
            "category": "Fraud Attack",
            "is_hard_negative": False,
            "description": "5 synchronized accounts sharing Device & IP, executing circular flow and elevated refund farming.",
        },
        {
            "id": "shared_device_ring",
            "name": "Shared Device Farm",
            "category": "Fraud Attack",
            "is_hard_negative": False,
            "description": "4 separate accounts operating from the same hardware device ID targeting one merchant.",
        },
        {
            "id": "refund_farming",
            "name": "Refund Farming Collusion",
            "category": "Fraud Attack",
            "is_hard_negative": False,
            "description": "Coordinated buyer-merchant collusion with 60%+ refund rate on shared infrastructure.",
        },
        {
            "id": "circular_flow",
            "name": "Circular Money Laundering Loop",
            "category": "Fraud Attack",
            "is_hard_negative": False,
            "description": "Round-trip transaction chain (A→B→C→D→A) with matched high-value amounts.",
        },
        {
            "id": "legit_family_business",
            "name": "Family Business (Hard Negative)",
            "category": "Legitimate Overlap",
            "is_hard_negative": True,
            "description": "Merchants sharing store device & IP, but with spread-out purchases from diverse buyers and normal refund rates.",
        },
        {
            "id": "legit_corporate_office",
            "name": "Corporate Office Subnet (Hard Negative)",
            "category": "Legitimate Overlap",
            "is_hard_negative": True,
            "description": "5 employees on same office IP using distinct personal devices to purchase from varied merchants.",
        },
    ]


@router.post("/run", response_model=ScenarioRunResponse)
async def run_scenario(req: ScenarioRunRequest, background_tasks: BackgroundTasks):
    """
    Launch a scenario simulation.
    
    Generates synthetic payments and feeds them into the real-time detection pipeline
    asynchronously so the frontend can watch events arrive via WebSocket.
    """
    stype = req.scenario_type.lower()
    if stype not in SCENARIO_GENERATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario type '{req.scenario_type}'. Available: {list(SCENARIO_GENERATORS.keys())}"
        )

    generator_fn, is_hn = SCENARIO_GENERATORS[stype]
    now = datetime.utcnow()
    events, meta, description = generator_fn(now)

    involved = list(set([e["buyer_id"] for e in events] + [e["merchant_id"] for e in events]))

    # Launch background event playback
    background_tasks.add_task(_stream_scenario_events, events, req.inter_event_delay_ms)

    return ScenarioRunResponse(
        scenario_id=meta.scenario_id,
        scenario_type=meta.scenario_type,
        status="running",
        total_events=len(events),
        accounts_involved=involved,
        description=description,
        is_hard_negative=is_hn,
    )
