"""
Configuration parameters for the synthetic data generator.

v2: Expanded population + richer hard-negative scenarios for honest FP evaluation.
"""

# ── Population ────────────────────────────────────────────────────────────────
NUM_MERCHANTS = 120         # legitimate merchant accounts
NUM_BUYERS    = 500         # legitimate buyer accounts
NUM_DEVICES   = 350         # unique devices in the legit population
NUM_IPS       = 280         # unique IP IDs in the legit population (exact IPs, not /16)

# Transaction generation
TXN_DAYS         = 90       # lookback window
AVG_TXN_PER_PAIR = 3        # average transactions per (buyer, merchant) pair
REFUND_RATE      = 0.03     # platform baseline refund rate (3%)

# ── Hard negatives (critical for honest FP story) ─────────────────────────────
# These are explicitly-labeled benign scenarios that produce shared-infrastructure
# signals similar to fraud rings. The system must NOT flag them.
#
# 1. Family business: legitimate merchants sharing one device + one IP
FAMILY_BUSINESS_COUNT    = 3    # merchants in the family business cluster
# 2. Corporate office: large group of buyers on the same company IP
CORPORATE_OFFICE_COUNT   = 25   # buyers on the same office subnet IP
# 3. Household: buyers sharing a home device and home IP (different from family biz)
HOUSEHOLD_GROUPS         = 3    # number of household groups
HOUSEHOLD_SIZE           = 3    # buyers per household
# 4. High-volume legitimate merchant: high txn velocity, no fraud signals
HIGH_VOLUME_MERCHANT_COUNT = 2  # extra "popular merchant" accounts
HIGH_VOLUME_TXN_FACTOR     = 5  # 5x more transactions than average
# 5. Elevated-return merchant: e.g. apparel/electronics, legitimate high refunds
ELEVATED_REFUND_MERCHANT_COUNT = 2   # merchants with legitimately high refund rates
ELEVATED_REFUND_RATE           = 0.22  # 22% refund rate (still well below 3× baseline)

# Legacy alias for backward compatibility
FAMILY_BUSINESS_COUNT_COMPAT = FAMILY_BUSINESS_COUNT
SHARED_OFFICE_IP_COUNT       = CORPORATE_OFFICE_COUNT

# ── Fraud rings ───────────────────────────────────────────────────────────────
# Parameterized variation: sizes randomized within ranges so the model must
# learn transferable patterns, not memorize one fixed ring template.
RINGS = {
    "shared_device": {
        "count":     4,          # rings of this type
        "size_min":  4,          # minimum accounts per ring
        "size_max":  7,          # maximum accounts per ring
        "size":      5,          # default (used when size_min==size_max)
    },
    "shared_ip": {
        "count":     3,
        "size_min":  4,
        "size_max":  7,
        "size":      5,
    },
    "collusion": {
        "count":         3,
        "buyers_min":    3,
        "buyers_max":    5,
        "merchants_min": 1,
        "merchants_max": 3,
        "buyers":        4,       # default
        "merchants":     2,       # default
        "txn_per_pair":  12,
        "refund_rate":   0.45,
    },
    "refund_farming": {
        "count":         3,
        "buyers_min":    3,
        "buyers_max":    5,
        "merchants_min": 1,
        "merchants_max": 2,
        "buyers":        3,
        "merchants":     1,
        "txn_per_pair":  20,
        "refund_rate":   0.55,
    },
    "circular_flow": {
        "count":     3,
        "size_min":  3,
        "size_max":  6,
        "size":      4,
    },
    "mixed_signal": {    # shared device + circular flow + elevated refund
        "count":     2,
        "size_min":  4,
        "size_max":  6,
        "size":      5,
    },
}

# ── Hero demo case (deterministic, hand-verified) ─────────────────────────────
# Injected as a fixed ring so the live demo always has a good example.
# Combines: shared device + shared IP + creation sync + circular flow + elevated refund
HERO_RING_SIZE       = 5
HERO_RING_ID         = "HERO"
HERO_REFUND_RATE     = 0.40
HERO_AMOUNT_BASE     = 25000.0    # ₹25,000 base circular flow amount
HERO_CREATION_SPREAD = 75         # seconds (tight sync)

# ── Evaluation split ──────────────────────────────────────────────────────────
TRAIN_FRACTION = 0.6         # fraction of legit clusters for IF training
RANDOM_SEED    = 42
