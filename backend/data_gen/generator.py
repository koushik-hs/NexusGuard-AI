"""
Synthetic data generator for the Coordinated Payment Abuse Detection System.

v2 changes:
  - Uses exact IP IDs throughout (no /16 range bucketing in generation)
  - Fraud rings properly register their shared IPs in the ips table
  - Rich hard-negative scenarios: corporate office, household, high-volume merchant,
    elevated-refund merchant — these are LABELED benign and must not be flagged
  - Parameterized ring variation (sizes, timing, noise) for generalization testing
  - Deterministic hero demo case injected with ring_id="HERO"

Outputs (to backend/data/):
  accounts.csv     — all accounts (merchant + buyer) with split labels
  devices.csv      — device records
  ips.csv          — IP records (exact IPs, not /16 ranges)
  transactions.csv — all transactions
  account_devices.csv — account↔device many-to-many
  account_ips.csv     — account↔IP many-to-many (ip_id is the exact-IP key)
  labels.csv          — ground-truth ring membership
  hero_accounts.json  — IDs of the hero demo ring members
"""

import os
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np

from data_gen.config import (
    NUM_MERCHANTS, NUM_BUYERS, NUM_DEVICES, NUM_IPS,
    TXN_DAYS, AVG_TXN_PER_PAIR, REFUND_RATE,
    FAMILY_BUSINESS_COUNT, CORPORATE_OFFICE_COUNT,
    HOUSEHOLD_GROUPS, HOUSEHOLD_SIZE,
    HIGH_VOLUME_MERCHANT_COUNT, HIGH_VOLUME_TXN_FACTOR,
    ELEVATED_REFUND_MERCHANT_COUNT, ELEVATED_REFUND_RATE,
    RINGS, RANDOM_SEED,
    HERO_RING_SIZE, HERO_RING_ID, HERO_REFUND_RATE,
    HERO_AMOUNT_BASE, HERO_CREATION_SPREAD,
)

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

BASE_TS = datetime(2024, 1, 1, 0, 0, 0)
END_TS  = BASE_TS + timedelta(days=TXN_DAYS)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(base: datetime, offset_days: float) -> str:
    return (base + timedelta(days=offset_days)).strftime("%Y-%m-%dT%H:%M:%S")


def _business_hour_offset(day: float) -> float:
    hour = random.gauss(13, 3)
    hour = max(0.0, min(23.99, hour))
    return day + hour / 24.0


def _random_ip(prefix: str = None) -> str:
    if prefix:
        octets = prefix.split(".")[:2]
        return f"{octets[0]}.{octets[1]}.{random.randint(0,255)}.{random.randint(1,254)}"
    return f"{random.randint(10,220)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _ip_range(ip: str) -> str:
    """Bucket an IP to its /16 range (kept for display only, NOT used for linking)."""
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.x.x"


def _amount() -> float:
    """Realistic transaction amount — log-normal distribution."""
    return round(np.random.lognormal(mean=6.5, sigma=1.2), 2)


# ── Counters ──────────────────────────────────────────────────────────────────
_account_counter     = 0
_device_counter      = 0
_ip_counter          = 0
_transaction_counter = 0
_ring_counter        = 0


def _next_account_id() -> str:
    global _account_counter
    _account_counter += 1
    return f"A{_account_counter:04d}"


def _next_device_id() -> str:
    global _device_counter
    _device_counter += 1
    return f"D{_device_counter:04d}"


def _next_ip_id() -> str:
    global _ip_counter
    _ip_counter += 1
    return f"IP{_ip_counter:04d}"


def _next_txn_id() -> str:
    global _transaction_counter
    _transaction_counter += 1
    return f"T{_transaction_counter:06d}"


def _next_ring_id() -> str:
    global _ring_counter
    _ring_counter += 1
    return f"R{_ring_counter:03d}"


def _rand_ring_size(cfg: dict) -> int:
    """Pick a ring size from configured range for parameterized variation."""
    lo = cfg.get("size_min", cfg.get("size", 5))
    hi = cfg.get("size_max", cfg.get("size", 5))
    return random.randint(lo, hi)


# ── Legitimate population ──────────────────────────────────────────────────────

def generate_legitimate_population():
    """
    Build the normal, non-fraudulent population.
    Includes deliberately-injected benign overlap cases (hard negatives).
    """
    accounts:     List[Dict] = []
    devices:      List[Dict] = []
    ips:          List[Dict] = []
    transactions: List[Dict] = []
    acct_devices: Dict[str, List[str]] = {}
    acct_ips:     Dict[str, List[str]] = {}

    # 1. Device pool
    device_pool = []
    for _ in range(NUM_DEVICES):
        did = _next_device_id()
        devices.append({"device_id": did,
                         "fingerprint": f"fp_{did}_{random.randint(100000,999999)}",
                         "is_fraud": False})
        device_pool.append(did)

    # 2. IP pool  (each ip_id is an exact IP address — no /16 bucketing)
    ip_pool = []
    for _ in range(NUM_IPS):
        iid = _next_ip_id()
        ip_addr  = _random_ip()
        ip_rng   = _ip_range(ip_addr)
        ips.append({"ip_id": iid, "ip_address": ip_addr, "ip_range": ip_rng, "is_fraud": False})
        ip_pool.append(iid)

    # 3. Merchant accounts
    merchant_ids = []
    for i in range(NUM_MERCHANTS):
        aid = _next_account_id()
        created_day = random.uniform(0, TXN_DAYS * 0.5)
        n_devs = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]
        my_devices = random.sample(device_pool, n_devs)
        n_ips = random.choices([1, 2], weights=[0.85, 0.15])[0]
        my_ips = random.sample(ip_pool, n_ips)
        acct_devices[aid] = my_devices
        acct_ips[aid]     = my_ips
        accounts.append({
            "account_id": aid, "type": "merchant",
            "created_at": _ts(BASE_TS, created_day),
            "is_fraud_ring_member": False, "ring_id": None,
            "is_benign_overlap": False,
            "benign_type": None,
        })
        merchant_ids.append(aid)

    # 4. Buyer accounts
    buyer_ids = []
    for _ in range(NUM_BUYERS):
        aid = _next_account_id()
        created_day = random.uniform(0, TXN_DAYS * 0.8)
        n_devs = random.choices([1, 2], weights=[0.90, 0.10])[0]
        my_devices = random.sample(device_pool, n_devs)
        n_ips = random.choices([1, 2, 3], weights=[0.70, 0.25, 0.05])[0]
        my_ips = random.sample(ip_pool, n_ips)
        acct_devices[aid] = my_devices
        acct_ips[aid]     = my_ips
        accounts.append({
            "account_id": aid, "type": "buyer",
            "created_at": _ts(BASE_TS, created_day),
            "is_fraud_ring_member": False, "ring_id": None,
            "is_benign_overlap": False,
            "benign_type": None,
        })
        buyer_ids.append(aid)

    # ── Hard negative 1: Family business ──────────────────────────────────────
    # Legitimate merchants sharing one dedicated device + one dedicated IP.
    # Uses fresh IDs NOT in the general pools to isolate the cluster.
    family_device = _next_device_id()
    devices.append({"device_id": family_device,
                     "fingerprint": f"fp_{family_device}_FAM",
                     "is_fraud": False})
    family_ip_id = _next_ip_id()
    fam_ip_addr = "192.168.10.50"
    ips.append({"ip_id": family_ip_id, "ip_address": fam_ip_addr,
                 "ip_range": _ip_range(fam_ip_addr), "is_fraud": False})
    family_merchants = random.sample(merchant_ids, FAMILY_BUSINESS_COUNT)
    for aid in family_merchants:
        acct_devices[aid] = [family_device]
        acct_ips[aid]     = [family_ip_id]
        for acc in accounts:
            if acc["account_id"] == aid:
                acc["is_benign_overlap"] = True
                acc["benign_type"]       = "family_business"

    # ── Hard negative 2: Corporate office ─────────────────────────────────────
    # Many buyers on the same company IP. Large enough to look suspicious on IP alone.
    office_ip_id = _next_ip_id()
    off_ip_addr  = "10.0.1.100"
    ips.append({"ip_id": office_ip_id, "ip_address": off_ip_addr,
                 "ip_range": _ip_range(off_ip_addr), "is_fraud": False})
    office_buyers = random.sample(buyer_ids, CORPORATE_OFFICE_COUNT)
    for aid in office_buyers:
        # Replace one of their IPs with the office IP; keep their device
        acct_ips[aid] = [office_ip_id]
        for acc in accounts:
            if acc["account_id"] == aid:
                acc["is_benign_overlap"] = True
                acc["benign_type"]       = "corporate_office"

    # ── Hard negative 3: Household ─────────────────────────────────────────────
    # Small groups of buyers sharing a home device + home IP.
    available_buyers = [b for b in buyer_ids
                        if b not in office_buyers and b not in family_merchants]
    for g in range(HOUSEHOLD_GROUPS):
        if len(available_buyers) < HOUSEHOLD_SIZE:
            break
        hh_device = _next_device_id()
        hh_ip_id  = _next_ip_id()
        hh_addr   = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"
        devices.append({"device_id": hh_device, "fingerprint": f"fp_{hh_device}_HH", "is_fraud": False})
        ips.append({"ip_id": hh_ip_id, "ip_address": hh_addr, "ip_range": _ip_range(hh_addr), "is_fraud": False})
        hh_members = available_buyers[:HOUSEHOLD_SIZE]
        available_buyers = available_buyers[HOUSEHOLD_SIZE:]
        for aid in hh_members:
            acct_devices[aid] = [hh_device]
            acct_ips[aid]     = [hh_ip_id]
            for acc in accounts:
                if acc["account_id"] == aid:
                    acc["is_benign_overlap"] = True
                    acc["benign_type"]       = "household"

    # ── Hard negative 4: High-volume legitimate merchant ───────────────────────
    # Some merchants are simply popular and have very high txn velocity.
    # They should NOT be flagged for velocity alone.
    hv_merchant_ids = random.sample(
        [m for m in merchant_ids if m not in family_merchants],
        min(HIGH_VOLUME_MERCHANT_COUNT, len(merchant_ids))
    )
    for aid in hv_merchant_ids:
        for acc in accounts:
            if acc["account_id"] == aid:
                acc["is_benign_overlap"] = True
                acc["benign_type"]       = "high_volume_merchant"

    # ── Hard negative 5: Elevated-refund merchant (legit apparel/electronics) ──
    er_merchant_ids = random.sample(
        [m for m in merchant_ids if m not in family_merchants and m not in hv_merchant_ids],
        min(ELEVATED_REFUND_MERCHANT_COUNT, len(merchant_ids))
    )
    for aid in er_merchant_ids:
        for acc in accounts:
            if acc["account_id"] == aid:
                acc["is_benign_overlap"] = True
                acc["benign_type"]       = "elevated_refund_merchant"

    # ── Generate regular transactions ──────────────────────────────────────────
    for buyer_id in buyer_ids:
        n_merchants = max(1, int(np.random.exponential(3)))
        n_merchants = min(n_merchants, len(merchant_ids))
        chosen_merchants = random.sample(merchant_ids, n_merchants)
        for merchant_id in chosen_merchants:
            # High-volume merchants get more transactions
            txn_mult = HIGH_VOLUME_TXN_FACTOR if merchant_id in hv_merchant_ids else 1
            n_txns   = max(1, np.random.poisson(AVG_TXN_PER_PAIR * txn_mult))
            for _ in range(n_txns):
                day    = random.uniform(0, TXN_DAYS)
                offset = _business_hour_offset(day)
                amount = _amount()
                # Elevated-refund merchants have realistic higher refund rates
                if merchant_id in er_merchant_ids:
                    is_refund = random.random() < ELEVATED_REFUND_RATE
                else:
                    is_refund = random.random() < REFUND_RATE
                transactions.append({
                    "txn_id": _next_txn_id(),
                    "buyer_id": buyer_id, "merchant_id": merchant_id,
                    "amount": amount,
                    "timestamp": _ts(BASE_TS, offset),
                    "is_refund": is_refund, "refund_of": None,
                    "ring_id": None, "is_fraud": False,
                })

    return (accounts, devices, ips, transactions,
            acct_devices, acct_ips,
            merchant_ids, buyer_ids,
            hv_merchant_ids, er_merchant_ids)


# ── Fraud ring injectors ───────────────────────────────────────────────────────

def _inject_shared_device_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    ip_pool, size: int, ring_id: str
) -> List[str]:
    """N buyer accounts sharing a single new device.
    
    Each member gets a DEDICATED IP (not from general pool) so the cluster
    stays tight and doesn't merge with the legitimate population via transitive
    IP sharing.  Device sharing is the fraud signal here.
    """
    did = _next_device_id()
    devices.append({"device_id": did, "fingerprint": f"fp_{did}_FRAUD", "is_fraud": True})

    ring_accounts = []
    base_ts = BASE_TS + timedelta(days=random.uniform(15, 70))
    time_spread = random.randint(30, 120)  # seconds of creation spread — tight sync
    for i in range(size):
        aid = _next_account_id()
        created_at = (base_ts + timedelta(seconds=random.randint(0, time_spread))).strftime("%Y-%m-%dT%H:%M:%S")
        # Dedicated IP per ring member — not from general pool
        # (prevents transitive merging with legitimate accounts)
        iid = _next_ip_id()
        ip_addr = _random_ip("172.18")   # dedicated fraud range
        ips.append({"ip_id": iid, "ip_address": ip_addr,
                     "ip_range": _ip_range(ip_addr), "is_fraud": True})
        acct_devices[aid] = [did]
        acct_ips[aid]     = [iid]
        accounts.append({
            "account_id": aid, "type": "buyer",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)



    legit_merchants = [a["account_id"] for a in accounts
                       if a["type"] == "merchant" and not a["is_fraud_ring_member"]]
    target_merchant = random.choice(legit_merchants)
    n_txns = random.randint(5, 15)
    for buyer_id in ring_accounts:
        for _ in range(n_txns):
            transactions.append({
                "txn_id": _next_txn_id(), "buyer_id": buyer_id,
                "merchant_id": target_merchant,
                "amount": _amount(),
                "timestamp": _ts(BASE_TS, random.uniform(0, TXN_DAYS)),
                "is_refund": random.random() < 0.05,
                "refund_of": None, "ring_id": ring_id, "is_fraud": True,
            })
    return ring_accounts


def _inject_shared_ip_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    device_pool, size: int, ring_id: str
) -> List[str]:
    """N merchant accounts sharing a dedicated exact IP."""
    # Create a NEW dedicated IP record and add it to ips list (fixes "unknown" bug)
    iid = _next_ip_id()
    shared_ip_addr = _random_ip("172.16")  # dedicated range distinct from legit pool
    ips.append({"ip_id": iid, "ip_address": shared_ip_addr,
                 "ip_range": _ip_range(shared_ip_addr), "is_fraud": True})

    ring_accounts = []
    base_ts = BASE_TS + timedelta(days=random.uniform(10, 50))
    time_spread = random.randint(30, 150)
    for _ in range(size):
        aid = _next_account_id()
        created_at = (base_ts + timedelta(seconds=random.randint(0, time_spread))).strftime("%Y-%m-%dT%H:%M:%S")
        # Dedicated device per member — not from general pool — IP is the only shared signal
        member_did = _next_device_id()
        devices.append({"device_id": member_did,
                         "fingerprint": f"fp_{member_did}_SIPRING", "is_fraud": True})
        acct_devices[aid] = [member_did]
        acct_ips[aid]     = [iid]      # ALL share exact same ip_id
        accounts.append({
            "account_id": aid, "type": "merchant",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)

    legit_buyers = [a["account_id"] for a in accounts
                    if a["type"] == "buyer" and not a["is_fraud_ring_member"]]
    sample_buyers = random.sample(legit_buyers, min(8, len(legit_buyers)))
    for buyer_id in sample_buyers:
        for merchant_id in ring_accounts:
            for _ in range(random.randint(2, 6)):
                transactions.append({
                    "txn_id": _next_txn_id(), "buyer_id": buyer_id,
                    "merchant_id": merchant_id,
                    "amount": _amount(),
                    "timestamp": _ts(BASE_TS, random.uniform(0, TXN_DAYS)),
                    "is_refund": False, "refund_of": None,
                    "ring_id": ring_id, "is_fraud": True,
                })
    return ring_accounts


def _inject_collusion_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    device_pool, ip_pool,
    n_buyers: int, n_merchants: int, txn_per_pair: int, refund_rate: float,
    ring_id: str
) -> List[str]:
    """Buyer-merchant collusion: shared device + high refund rate."""
    ring_accounts = []
    base_ts = BASE_TS + timedelta(days=random.uniform(20, 60))
    time_spread = random.randint(60, 300)

    did = _next_device_id()
    devices.append({"device_id": did, "fingerprint": f"fp_{did}_COLLUDE", "is_fraud": True})

    # Shared IP for collusion ring (all on same IP too)
    iid = _next_ip_id()
    col_ip = _random_ip("10.1")
    ips.append({"ip_id": iid, "ip_address": col_ip, "ip_range": _ip_range(col_ip), "is_fraud": True})

    for _ in range(n_buyers):
        aid = _next_account_id()
        created_at = (base_ts + timedelta(seconds=random.randint(0, time_spread))).strftime("%Y-%m-%dT%H:%M:%S")
        acct_devices[aid] = [did]
        acct_ips[aid]     = [iid]
        accounts.append({
            "account_id": aid, "type": "buyer",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)

    for _ in range(n_merchants):
        aid = _next_account_id()
        created_at = (base_ts + timedelta(seconds=random.randint(0, time_spread))).strftime("%Y-%m-%dT%H:%M:%S")
        acct_devices[aid] = [did]
        acct_ips[aid]     = [iid]
        accounts.append({
            "account_id": aid, "type": "merchant",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)

    buyer_ring    = ring_accounts[:n_buyers]
    merchant_ring = ring_accounts[n_buyers:]
    for buyer_id in buyer_ring:
        for merchant_id in merchant_ring:
            for _ in range(txn_per_pair):
                amount = round(random.uniform(500, 5000), 2)
                transactions.append({
                    "txn_id": _next_txn_id(), "buyer_id": buyer_id,
                    "merchant_id": merchant_id,
                    "amount": amount,
                    "timestamp": _ts(BASE_TS, random.uniform(0, TXN_DAYS)),
                    "is_refund": random.random() < refund_rate,
                    "refund_of": None, "ring_id": ring_id, "is_fraud": True,
                })
    return ring_accounts


def _inject_refund_farming_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    device_pool, ip_pool, n_buyers, n_merchants, txn_per_pair, refund_rate, ring_id
) -> List[str]:
    """Refund farming: collusion pattern with very high refund rate."""
    return _inject_collusion_ring(
        accounts, devices, ips, transactions, acct_devices, acct_ips,
        device_pool, ip_pool,
        n_buyers, n_merchants, txn_per_pair, refund_rate, ring_id
    )


def _inject_circular_flow_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    device_pool, ip_pool, size: int, ring_id: str
) -> List[str]:
    """Circular money flow: A→B→C→A with near-matching amounts."""
    ring_accounts = []
    base_ts = BASE_TS + timedelta(days=random.uniform(15, 70))
    time_spread = random.randint(1800, 172800)   # 30 min to 2 days (less tight than device rings)

    did = _next_device_id()
    devices.append({"device_id": did, "fingerprint": f"fp_{did}_CIRC", "is_fraud": True})
    iid = _next_ip_id()
    circ_ip = _random_ip("10.2")
    ips.append({"ip_id": iid, "ip_address": circ_ip, "ip_range": _ip_range(circ_ip), "is_fraud": True})

    for i in range(size):
        aid = _next_account_id()
        created_at = (base_ts + timedelta(seconds=random.randint(0, time_spread))).strftime("%Y-%m-%dT%H:%M:%S")
        acct_devices[aid] = [did]
        acct_ips[aid]     = [iid]
        accounts.append({
            "account_id": aid, "type": "merchant",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)

    base_amount     = round(random.uniform(10000, 50000), 2)
    cycle_start_day = random.uniform(5, TXN_DAYS - 5)
    for i in range(size):
        buyer_id    = ring_accounts[i]
        merchant_id = ring_accounts[(i + 1) % size]
        amount      = round(base_amount * random.uniform(0.97, 1.03), 2)
        transactions.append({
            "txn_id": _next_txn_id(), "buyer_id": buyer_id,
            "merchant_id": merchant_id, "amount": amount,
            "timestamp": _ts(BASE_TS, cycle_start_day + i * 0.01),
            "is_refund": False, "refund_of": None,
            "ring_id": ring_id, "is_fraud": True,
        })
    # Noise transactions
    for _ in range(15):
        buyer_id    = random.choice(ring_accounts)
        merchant_id = random.choice(ring_accounts)
        if buyer_id == merchant_id:
            continue
        transactions.append({
            "txn_id": _next_txn_id(), "buyer_id": buyer_id,
            "merchant_id": merchant_id, "amount": _amount(),
            "timestamp": _ts(BASE_TS, random.uniform(0, TXN_DAYS)),
            "is_refund": False, "refund_of": None,
            "ring_id": ring_id, "is_fraud": True,
        })
    return ring_accounts


def _inject_mixed_signal_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    device_pool, ip_pool, size: int, ring_id: str
) -> List[str]:
    """Mixed: shared device + shared IP + circular flow + elevated refund."""
    ring_accounts = []
    base_ts = BASE_TS + timedelta(days=random.uniform(10, 60))
    time_spread = random.randint(20, 60)  # very tight creation sync

    did = _next_device_id()
    devices.append({"device_id": did, "fingerprint": f"fp_{did}_MIX", "is_fraud": True})
    iid = _next_ip_id()
    mix_ip = _random_ip("10.3")
    ips.append({"ip_id": iid, "ip_address": mix_ip, "ip_range": _ip_range(mix_ip), "is_fraud": True})

    for _ in range(size):
        aid = _next_account_id()
        created_at = (base_ts + timedelta(seconds=random.randint(0, time_spread))).strftime("%Y-%m-%dT%H:%M:%S")
        acct_devices[aid] = [did]
        acct_ips[aid]     = [iid]
        accounts.append({
            "account_id": aid, "type": "merchant",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)

    base_amount     = round(random.uniform(5000, 20000), 2)
    cycle_start_day = random.uniform(5, TXN_DAYS - 2)
    for i in range(size):
        buyer_id    = ring_accounts[i]
        merchant_id = ring_accounts[(i + 1) % size]
        amount      = round(base_amount * random.uniform(0.98, 1.02), 2)
        transactions.append({
            "txn_id": _next_txn_id(), "buyer_id": buyer_id,
            "merchant_id": merchant_id, "amount": amount,
            "timestamp": _ts(BASE_TS, cycle_start_day + i * 0.005),
            "is_refund": False, "refund_of": None,
            "ring_id": ring_id, "is_fraud": True,
        })

    legit_buyers = [a["account_id"] for a in accounts
                    if a["type"] == "buyer" and not a["is_fraud_ring_member"]]
    sample_buyers = random.sample(legit_buyers, min(5, len(legit_buyers)))
    for buyer_id in sample_buyers:
        merchant_id = random.choice(ring_accounts)
        for _ in range(8):
            transactions.append({
                "txn_id": _next_txn_id(), "buyer_id": buyer_id,
                "merchant_id": merchant_id,
                "amount": round(random.uniform(200, 2000), 2),
                "timestamp": _ts(BASE_TS, random.uniform(0, TXN_DAYS)),
                "is_refund": random.random() < 0.45,
                "refund_of": None, "ring_id": ring_id, "is_fraud": True,
            })
    return ring_accounts


def _inject_hero_ring(
    accounts, devices, ips, transactions, acct_devices, acct_ips,
    merchant_ids: List[str],
) -> List[str]:
    """
    Deterministic hero demo ring — combines ALL major signals:
      shared device + shared IP + creation sync + circular flow + elevated refund
      + high merchant concentration

    Always injected with ring_id="HERO" at a fixed timestamp for demo reproducibility.
    Risk score should reliably land in the Critical band (≥85).
    """
    size    = HERO_RING_SIZE
    ring_id = HERO_RING_ID

    # Dedicated device and IP — not shared with anything else
    hero_device = _next_device_id()
    hero_ip_id  = _next_ip_id()
    hero_ip_addr = "172.31.250.100"   # distinctive address for easy demo identification
    devices.append({"device_id": hero_device,
                     "fingerprint": f"fp_{hero_device}_HERO", "is_fraud": True})
    ips.append({"ip_id": hero_ip_id, "ip_address": hero_ip_addr,
                 "ip_range": _ip_range(hero_ip_addr), "is_fraud": True})

    # Fixed base timestamp for reproducibility
    base_ts = BASE_TS + timedelta(days=45)   # mid-dataset
    ring_accounts = []
    for i in range(size):
        aid = _next_account_id()
        # All created within HERO_CREATION_SPREAD seconds — tight sync
        created_at = (base_ts + timedelta(seconds=i * (HERO_CREATION_SPREAD // size))).strftime("%Y-%m-%dT%H:%M:%S")
        acct_devices[aid] = [hero_device]
        acct_ips[aid]     = [hero_ip_id]
        accounts.append({
            "account_id": aid, "type": "merchant",
            "created_at": created_at,
            "is_fraud_ring_member": True, "ring_id": ring_id,
            "is_benign_overlap": False, "benign_type": None,
        })
        ring_accounts.append(aid)

    # Circular flow: A→B→C→D→E→A
    cycle_day = 45.5   # day 45 of the dataset, immediately after creation
    for i in range(size):
        buyer_id    = ring_accounts[i]
        merchant_id = ring_accounts[(i + 1) % size]
        amount      = round(HERO_AMOUNT_BASE * random.uniform(0.98, 1.02), 2)
        transactions.append({
            "txn_id": _next_txn_id(), "buyer_id": buyer_id,
            "merchant_id": merchant_id, "amount": amount,
            "timestamp": _ts(BASE_TS, cycle_day + i * 0.001),
            "is_refund": False, "refund_of": None,
            "ring_id": ring_id, "is_fraud": True,
        })

    # High-refund transactions from ring members with external merchants
    # concentrated on ONE legitimate merchant
    target_merchant = merchant_ids[0]   # deterministic target
    for member_id in ring_accounts:
        for j in range(10):
            transactions.append({
                "txn_id": _next_txn_id(), "buyer_id": member_id,
                "merchant_id": target_merchant,
                "amount": round(random.uniform(1000, 8000), 2),
                "timestamp": _ts(BASE_TS, 45 + j * 0.5),
                "is_refund": random.random() < HERO_REFUND_RATE,
                "refund_of": None, "ring_id": ring_id, "is_fraud": True,
            })

    return ring_accounts


# ── Link-table builder ─────────────────────────────────────────────────────────

def _build_link_tables(acct_devices: Dict, acct_ips: Dict,
                        all_devices: List[Dict], all_ips: List[Dict]):
    """Build account↔device and account↔IP many-to-many link records."""
    dev_map = {d["device_id"]: d for d in all_devices}
    ip_map  = {i["ip_id"]: i for i in all_ips}

    acct_device_links = []
    for aid, dev_ids in acct_devices.items():
        for did in dev_ids:
            acct_device_links.append({"account_id": aid, "device_id": did})

    acct_ip_links = []
    for aid, ip_ids in acct_ips.items():
        for iid in ip_ids:
            if iid in ip_map:
                acct_ip_links.append({
                    "account_id": aid, "ip_id": iid,
                    "ip_range": ip_map[iid]["ip_range"],
                })
            else:
                # Should not happen in v2 — all IPs are registered
                acct_ip_links.append({"account_id": aid, "ip_id": iid, "ip_range": "unknown"})

    return acct_device_links, acct_ip_links


# ── Main entry point ───────────────────────────────────────────────────────────

def generate():
    print("[generator] Building legitimate population...")
    (accounts, devices, ips, transactions,
     acct_devices, acct_ips,
     merchant_ids, buyer_ids,
     hv_merchant_ids, er_merchant_ids) = generate_legitimate_population()

    device_pool = [d["device_id"] for d in devices if not d["is_fraud"]]
    ip_pool     = [i["ip_id"]     for i in ips     if not i["is_fraud"]]

    ring_membership: List[Dict] = []

    print("[generator] Injecting fraud rings...")

    # Shared-device rings (parameterized sizes)
    for _ in range(RINGS["shared_device"]["count"]):
        rid  = _next_ring_id()
        size = _rand_ring_size(RINGS["shared_device"])
        members = _inject_shared_device_ring(
            accounts, devices, ips, transactions, acct_devices, acct_ips,
            ip_pool, size=size, ring_id=rid
        )
        for aid in members:
            ring_membership.append({"account_id": aid, "ring_id": rid, "ring_type": "shared_device"})

    # Shared-IP rings
    for _ in range(RINGS["shared_ip"]["count"]):
        rid  = _next_ring_id()
        size = _rand_ring_size(RINGS["shared_ip"])
        members = _inject_shared_ip_ring(
            accounts, devices, ips, transactions, acct_devices, acct_ips,
            device_pool, size=size, ring_id=rid
        )
        for aid in members:
            ring_membership.append({"account_id": aid, "ring_id": rid, "ring_type": "shared_ip"})

    # Collusion rings
    cfg = RINGS["collusion"]
    for _ in range(cfg["count"]):
        rid  = _next_ring_id()
        n_b  = random.randint(cfg["buyers_min"],    cfg["buyers_max"])
        n_m  = random.randint(cfg["merchants_min"], cfg["merchants_max"])
        members = _inject_collusion_ring(
            accounts, devices, ips, transactions, acct_devices, acct_ips,
            device_pool, ip_pool,
            n_buyers=n_b, n_merchants=n_m,
            txn_per_pair=cfg["txn_per_pair"], refund_rate=cfg["refund_rate"],
            ring_id=rid
        )
        for aid in members:
            ring_membership.append({"account_id": aid, "ring_id": rid, "ring_type": "collusion"})

    # Refund farming rings
    cfg = RINGS["refund_farming"]
    for _ in range(cfg["count"]):
        rid  = _next_ring_id()
        n_b  = random.randint(cfg["buyers_min"],    cfg["buyers_max"])
        n_m  = random.randint(cfg["merchants_min"], cfg["merchants_max"])
        members = _inject_refund_farming_ring(
            accounts, devices, ips, transactions, acct_devices, acct_ips,
            device_pool, ip_pool,
            n_buyers=n_b, n_merchants=n_m,
            txn_per_pair=cfg["txn_per_pair"], refund_rate=cfg["refund_rate"],
            ring_id=rid
        )
        for aid in members:
            ring_membership.append({"account_id": aid, "ring_id": rid, "ring_type": "refund_farming"})

    # Circular flow rings
    cfg = RINGS["circular_flow"]
    for _ in range(cfg["count"]):
        rid  = _next_ring_id()
        size = _rand_ring_size(cfg)
        members = _inject_circular_flow_ring(
            accounts, devices, ips, transactions, acct_devices, acct_ips,
            device_pool, ip_pool, size=size, ring_id=rid
        )
        for aid in members:
            ring_membership.append({"account_id": aid, "ring_id": rid, "ring_type": "circular_flow"})

    # Mixed-signal rings
    cfg = RINGS["mixed_signal"]
    for _ in range(cfg["count"]):
        rid  = _next_ring_id()
        size = _rand_ring_size(cfg)
        members = _inject_mixed_signal_ring(
            accounts, devices, ips, transactions, acct_devices, acct_ips,
            device_pool, ip_pool, size=size, ring_id=rid
        )
        for aid in members:
            ring_membership.append({"account_id": aid, "ring_id": rid, "ring_type": "mixed_signal"})

    # Hero demo ring (always last, deterministic)
    hero_members = _inject_hero_ring(
        accounts, devices, ips, transactions, acct_devices, acct_ips, merchant_ids
    )
    for aid in hero_members:
        ring_membership.append({"account_id": aid, "ring_id": HERO_RING_ID, "ring_type": "mixed_signal"})

    # Build link tables
    acct_device_links, acct_ip_links = _build_link_tables(
        acct_devices, acct_ips, devices, ips
    )

    # ── Write CSVs ────────────────────────────────────────────────────────────
    print("[generator] Writing data files...")
    pd.DataFrame(accounts).to_csv(os.path.join(DATA_DIR, "accounts.csv"),         index=False)
    pd.DataFrame(devices).to_csv(os.path.join(DATA_DIR, "devices.csv"),           index=False)
    pd.DataFrame(ips).to_csv(os.path.join(DATA_DIR, "ips.csv"),                   index=False)
    pd.DataFrame(transactions).to_csv(os.path.join(DATA_DIR, "transactions.csv"), index=False)
    pd.DataFrame(acct_device_links).to_csv(os.path.join(DATA_DIR, "account_devices.csv"), index=False)
    pd.DataFrame(acct_ip_links).to_csv(os.path.join(DATA_DIR, "account_ips.csv"),         index=False)
    pd.DataFrame(ring_membership).to_csv(os.path.join(DATA_DIR, "labels.csv"),    index=False)

    # Save hero member IDs for the API
    with open(os.path.join(DATA_DIR, "hero_accounts.json"), "w") as f:
        json.dump({"ring_id": HERO_RING_ID, "members": hero_members}, f, indent=2)

    # Summary
    df_acct = pd.DataFrame(accounts)
    df_txn  = pd.DataFrame(transactions)
    n_benign = sum(1 for a in accounts if a.get("is_benign_overlap"))
    print(f"[generator] [OK] Accounts: {len(accounts)} "
          f"({df_acct[df_acct.type=='merchant'].shape[0]} merchants, "
          f"{df_acct[df_acct.type=='buyer'].shape[0]} buyers)")
    print(f"[generator] [OK] Devices: {len(devices)}")
    print(f"[generator] [OK] IPs: {len(ips)}")
    print(f"[generator] [OK] Transactions: {len(transactions)}")
    print(f"[generator] [OK] Fraud ring members: {len(ring_membership)}")
    print(f"[generator] [OK] Rings injected: {_ring_counter} + HERO")
    print(f"[generator] [OK] Benign-overlap accounts: {n_benign}")
    print(f"[generator] [OK] Hero ring members: {hero_members}")
    print(f"[generator] Data written to: {DATA_DIR}")
    return DATA_DIR


if __name__ == "__main__":
    generate()
