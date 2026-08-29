# NexusGuard AI — Real-Time Coordinated Payment Abuse Detection
### Razorpay AI Buildathon — Track 02: AI Risk Manager

> **Core Thesis:** Individual transactions inside an organized fraud ring frequently appear benign in isolation. The hidden relationships between accounts, merchants, device fingerprints, and network identifiers — the *dynamic entity graph* — reveal coordinated abuse that isolated per-transaction models cannot detect.

---

## 1. Detection & Baseline Performance (Actual Code Execution on Synthetic Data)

All reported metrics are computed via `python -m evaluation.evaluator` evaluating the active ML models and detection pipeline. **Zero placeholder values.**

| Metric | BL1: Txn-Only IF | BL2: Rule-Only Graph | BL3: IF-Only Graph | BL4: XGBoost Supervised | **Final: 3-Model Hybrid** |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Precision** | 76.4% | 81.8% | 14.6% | **100.0%** | **84.5%** |
| **Recall** | 56.1% | 82.7% | 100.0% | **100.0%** | **100.0%** |
| **F1 Score** | 64.7% | 82.2% | 25.4% | **100.0%** | **91.6%** |
| **False Positive Rate** | 2.7% | 2.9% | 92.7% | **0.0%** | **2.9%** |
| **PR-AUC** | 0.5966 | 0.9717 | 0.7261 | **1.0000** | **1.0000** |
| **ROC-AUC** | — | — | — | **1.0000** | **1.0000** |

### Ring-Level Recall: 100% (19 / 19 Fraud Rings Detected)
- **Shared Device Rings:** 4/4 (100%)
- **Shared IP Rings:** 3/3 (100%)
- **Buyer-Merchant Collusion:** 3/3 (100%)
- **Refund Farming Clusters:** 3/3 (100%)
- **Circular Money Flow (Round-Trip):** 3/3 (100%)
- **Mixed Multi-Signal Rings:** 3/3 (100%)

### Hard Negative Evaluation (Deliberate Benign Overlap Scenarios)
| Benign Archetype | Injected Population | Flagged Accounts | False Positive Rate |
|:---|:---:|:---:|:---:|
| **Family Business** (Shared device & IP) | 3 | 0 | **0.0%** |
| **Household Cluster** (Shared home network) | 9 | 0 | **0.0%** |
| **High-Volume Legitimate Merchant** | 2 | 0 | **0.0%** |
| **Elevated Return/Refund Merchant** | 2 | 0 | **0.0%** |
| **Corporate Office Subnet** | 25 | 1 | **4.0%** |
| **Overall Benign Overlap FPR** | **41** | **1** | **2.44%** |

---

## 2. Architecture & Real-Time Pipeline

```
  Real-Time Telemetry Stream               Batch Baseline Storage
  (Manual UI / Scenario Simulator)        (CSV Snapshots + Model Artifacts)
                 │                                        │
                 ▼                                        ▼
    ┌───────────────────────────┐           ┌───────────────────────────┐
    │   PublicEvent Type        │           │   Supervised XGBoost      │
    │   Boundary (No Labels)    │           │   + Unsupervised IF Model │
    └────────────┬──────────────┘           └─────────────┬─────────────┘
                 │                                        │
                 ▼                                        │
    ┌───────────────────────────┐                         │
    │   In-Memory LiveGraphState│ ◀───────────────────────┘
    │   • Incremental Telemetry │
    │   • NetworkX Subgraph     │
    │   • Louvain Partitioning  │
    └────────────┬──────────────┘
                 │
                 ▼
    ┌───────────────────────────┐
    │   18-Feature Extractor    │
    │   • Device/IP Clustering  │
    │   • Cycle Length (DFS)    │
    │   • Temporal Sync Ratio   │
    │   • Refund Elevation      │
    └────────────┬──────────────┘
                 │
                 ▼
    ┌───────────────────────────┐
    │   Hybrid Risk Scorer      │
    │   • 40% XGBoost Prob      │
    │   • 35% IF Anomaly Score  │
    │   • 25% Structural Rules  │
    │   • Large-Sparse Cap (≤35)│
    └────────────┬──────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
 ┌──────────────┐  ┌────────────────┐
 │ WebSocket WS │  │ REST API Engine│
 │  (/api/ws)   │  │  (FastAPI v3)  │
 └──────┬───────┘  └───────┬────────┘
        │                  │
        └─────────┬────────┘
                  ▼
    ┌───────────────────────────┐
    │  React 19 / Vite TSX UI   │
    │  • Live Event Stream Feed │
    │  • Risk Evolution Timeline│
    │  • Manual Event Simulator │
    │  • D3 Graph Explorer      │
    │  • Grounded AI Analyst    │
    └───────────────────────────┘
```

---

## 3. Threat Model & Security Scope

### Abuse Patterns Handled Effectively:
1. **Rapid Multi-Account Burst Creation:** Synchronized batch registration ($\le 300\text{s}$) detected via creation-time variance features.
2. **Infrastructure Reuse & Device Farms:** Hardware fingerprint sharing across accounts with density decay and weighted graph projections.
3. **Collusive Refund Farming:** High refund ratios paired with shared infrastructure or concentrated counterparty funnels.
4. **Circular Money Laundering:** Closed directed cycles ($A \to B \to C \to D \to A$) detected via cycle analysis on weighted transaction subgraphs.
5. **Corporate Proxy / Family Business Hard Negatives:** Disentangles benign network sharing from coordinated fraud using creation-spread modifiers and merchant entropy.

### Known Limitations (What This Detector Does NOT Cover):
1. **Slow Sleeper Fraud (Multi-Year Aging):** Accounts created years apart with organic transaction history before sudden collusion evade creation-time sync features.
2. **Advanced Hardware Fingerprint Spoofing:** Emulators rotating Canvas/WebGL hashes and device IDs per transaction will not trigger device-sharing edges without IP or behavioral overlap.
3. **Multi-Hop Money Mule Layering through Legitimate Merchants:** Layering schemes that route funds through intermediary legitimate merchants rather than direct P2P loops require cross-merchant platform visibility.
4. **Synthetic Data Evaluation Notice:** The system is evaluated on rigorous synthetic distributions. Real-world production deployment requires calibration on historical fraud chargebacks, continuous retraining, and human-in-the-loop analyst verification.

---

## 4. Automated Robustness & Ground-Truth Boundary Tests

Automated regression and counterfactual tests (`pytest tests -v`):
- **Order-Invariance Test (`test_order_sensitivity.py`):** Verified that feeding identical transactions in reverse/interleaved order yields substantially consistent final risk scores ($\le 15\text{pt}$ delta).
- **Infrastructure Ablation Counterfactual (`test_counterfactuals.py`):** Proves that swapping shared hardware devices for distinct devices drops risk by $\ge 20\text{ points}$.
- **Temporal Spread Counterfactual (`test_counterfactuals.py`):** Proves that spreading transactions across 60 days reduces temporal sync risk compared to 2-minute bursts.
- **Corporate Office Hard Negative (`test_counterfactuals.py`):** Asserts that 5 employees shopping at diverse stores on an office IP are evaluated as Low Risk ($< 40$).
- **Ground-Truth Boundary Audit (`test_ground_truth_boundary.py`):** Structural code audit verifying `PublicEvent` has no label attributes and models never query ground truth during inference.

---

## 5. Getting Started & Running Locally (100% Offline Compatible)

> [!NOTE]
> **Zero External Dependencies / API Keys Required:** NexusGuard AI is designed to run completely offline. ML models (XGBoost, Isolation Forest) and the detection engine run locally. The GenAI investigation engine defaults to deterministic, hallucination-guarded template reports if no `OPENAI_API_KEY` is provided.

### Prerequisites
- **Python**: 3.9+ (`pip` installed)
- **Node.js**: 18+ (`npm` installed)

---

### Quickstart (2 Terminals)

#### Terminal 1 — Backend (FastAPI + Live Graph Engine + WebSocket)
```bash
cd backend
pip install -r requirements.txt

# Start the server (auto-bootstraps data, trains models, and initializes live graph on first run)
uvicorn api.main:app --reload --port 8000
```
*Backend runs on: `http://localhost:8000` (API Docs: `http://localhost:8000/docs`)*

#### Terminal 2 — Frontend (React 19 Dashboard)
```bash
cd frontend
npm install
npm run dev
```
*Dashboard runs on: `http://localhost:5173`*

---

### Verification & Testing Commands

To independently execute each component or verify the detection metrics and robustness tests:

```bash
cd backend

# 1. Run Automated Robustness & Ground-Truth Boundary Test Suite
pytest tests -v

# 2. Train Supervised XGBoost + Unsupervised Isolation Forest Models
python -m ml.train

# 3. Run Batch Graph Detection Pipeline
python -m detection.pipeline

# 4. Run Formal 5-Baseline Evaluation & Metric Generation
python -m evaluation.evaluator

# 5. Run Feature Ablation Study
python -m ml.feature_ablation
```

---

*NexusGuard AI — Built for Razorpay AI Buildathon (Track 02: AI Risk Manager)*
