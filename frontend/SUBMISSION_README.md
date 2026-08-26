# NEXUSGUARD AI
### Payment Risk Intelligence Platform · Razorpay AI Buildathon 2026 · Track 02: AI Risk Manager

**NEXUSGUARD AI detects coordinated payment abuse that transaction-by-transaction scoring misses.** It builds a live relationship graph across buyer and merchant accounts, devices, IPs, and payments; scores suspicious clusters with a hybrid ML and rules engine; and gives an analyst the evidence needed to investigate.

> Individual payments can appear legitimate. The fraud signal is often the structure connecting them.

## Why this matters

Payment abuse is not always one anomalous card swipe. Fraud rings can distribute activity across accounts so that each event looks normal, while their shared infrastructure, transaction concentration, refund behavior, timing, or circular money flow reveals coordination.

NEXUSGUARD AI is designed to surface that relationship-level risk for analyst review. It covers shared-device farms, shared-IP coordination, buyer–merchant collusion, refund farming, circular flows, and mixed-signal rings—while deliberately testing benign shared-infrastructure cases such as family businesses and corporate office networks.

## What the product does

- Ingests a real payment event through `POST /api/events/submit`.
- Updates the in-memory relationship graph and recalculates affected-cluster features.
- Combines XGBoost, Isolation Forest, and structural rules into a 0–100 risk score.
- Returns an actual risk delta, evidence, alert decision, and measured processing-latency breakdown.
- Broadcasts the update through WebSocket to the React investigation console.
- Supports a manual event simulator and six scenario streams through the same ingestion path.
- Produces an evidence-grounded investigation report; the LLM explains evidence and **does not** classify fraud.

## Architecture

```text
Payment event / scenario
        │
        ▼
Public event boundary (no fraud labels)
        │
        ▼
Live graph state ── Accounts · Devices · IPs · Transactions
        │
        ▼
Graph, infrastructure, velocity, refund and temporal features
        │
        ├── XGBoost              supervised pattern signal
        ├── Isolation Forest     anomaly signal
        └── Structural rules     auditable domain evidence
        │
        ▼
Hybrid risk engine → evidence → alert → WebSocket → analyst console
                                      │
                                      ▼
                         grounded investigation report
```

### Design decisions

| Component | Why it exists |
|---|---|
| Heterogeneous graph | Shared infrastructure and multi-hop relationships are first-class signals. |
| XGBoost | Captures non-linear combinations of graph and payment features. |
| Isolation Forest | Adds sensitivity to anomalous patterns outside supervised examples. |
| Structural rules | Ensures every alert has inspectable domain evidence. |
| LLM investigator | Summarises structured evidence for a human; it has no classification or enforcement authority. |
| Hard negatives | Tests that shared IP/device alone is not treated as fraud. |

The hybrid score is **0.35 × Isolation Forest + 0.40 × XGBoost + 0.25 × structural rules**, with a fallback to **0.40 × Isolation Forest + 0.60 × rules** if XGBoost is unavailable.

## Evaluation snapshot

All values below are read from the repository's generated `backend/data/evaluation_results.json`. The dataset is synthetic; these figures demonstrate the methodology, not production performance.

| Detector | Precision | Recall | F1 | PR-AUC | False-positive rate |
|---|---:|---:|---:|---:|---:|
| Transaction-only baseline | 76.39% | 56.12% | 64.71% | 0.5966 | 2.74% |
| Rule-only graph detector | 81.82% | 82.65% | 82.23% | 0.9717 | 2.90% |
| Isolation Forest only | 14.56% | 100.00% | 25.42% | 0.7261 | 92.74% |
| XGBoost-only graph detector | 100.00% | 100.00% | 100.00% | 1.0000 | 0.00% |
| **Final hybrid detector** | **84.48%** | **100.00%** | **91.59%** | **1.0000** | **2.90%** |

Additional checks from the same evaluation run:

- **19 / 19** injected fraud rings detected at ring level.
- **1 / 41** deliberately injected benign-overlap accounts flagged: **2.44%** benign-overlap FPR.
- Ring types reported: shared device, shared IP, collusion, refund farming, circular flow, and mixed signal.

The perfect XGBoost result should be interpreted cautiously: it comes from synthetic data, not real Razorpay traffic. The project therefore exposes model breakdowns, hard-negative analysis, and limitations rather than presenting a risk score as a fraud verdict.

## Trust and safety boundaries

This is an analyst decision-support prototype, not an autonomous enforcement system.

- The public ingestion boundary accepts no fraud labels; generated labels are restricted to dataset generation and evaluation.
- The LLM receives structured detection evidence and is not the fraud classifier.
- Investigation reports recommend human-reviewed actions only; they do not freeze accounts, reverse funds, or take irreversible action.
- A deterministic template report is available when `OPENAI_API_KEY` is not configured or an LLM request fails.
- The project is strictly defensive and contains no fraud-execution, evasion, or control-bypass functionality.

## Analyst console

The React + TypeScript interface includes:

- **Overview** — current ring inventory, risk distribution, model signals, and engine totals.
- **Live Monitor** — WebSocket event feed, measured latency, alert filtering, and scenario launcher.
- **Graph Explorer** — focused subgraph investigation with typed entities and suspicious edges.
- **Detection Models** — baseline comparison, ring recall, and benign-overlap false-positive analysis.
- **Event Simulator** — submit a real event and inspect returned risk, delta, evidence, model context, and latency.
- **Ring Investigation** — evidence, features, graph context, and an investigation report for a selected ring.

## Quick start

Prerequisites: Python 3.9+ and Node.js 20+.

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open the Vite URL printed by the frontend (normally `http://localhost:5173`). The API runs at `http://localhost:8000`; its interactive API documentation is available at `http://localhost:8000/docs`.

On first startup, the backend creates missing synthetic data, ring results, and evaluation output, then initializes the live graph state.

### Rebuild synthetic artifacts

Use this only when intentionally regenerating the full synthetic dataset and model artifacts:

```bash
cd backend
python -m data_gen.generator
python -m ml.train
python -m detection.pipeline
python -m evaluation.evaluator
```

### Run the checks

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run build
```

## Demo path

1. Open **Live Monitor** and confirm the API and WebSocket status.
2. Launch **Family Business** or **Corporate Office** to demonstrate a hard negative.
3. Launch **Coordinated Ring** or submit the sequential shared-device manual events.
4. Watch the real events enter the stream; inspect the risk delta and generated evidence.
5. Open the relevant **Graph Explorer** view to inspect relationships.
6. Open **Detection Models** to compare the graph-aware hybrid system with the transaction-only baseline and review false-positive analysis.
7. Open a **Ring Investigation** report to show that the LLM explains structured evidence rather than classifying fraud.

## API surface

| Endpoint | Purpose |
|---|---|
| `GET /health` | API, generated-artifact, and live-engine readiness. |
| `GET /api/rings` | Risk-sorted detected rings. |
| `GET /api/rings/{ring_id}` | Ring features and structured evidence. |
| `GET /api/rings/{ring_id}/graph` | Focused graph nodes and edges. |
| `POST /api/rings/{ring_id}/investigate` | Evidence-grounded analyst report. |
| `GET /api/metrics` | Evaluation and baseline metrics. |
| `POST /api/events/submit` | Real-time payment-event ingestion. |
| `GET /api/events/stream` | Recent processed event history. |
| `GET /api/events/status` | Live graph-engine status. |
| `POST /api/scenarios/run` | Launch a real scenario through the common pipeline. |
| `WS /api/ws` | Real-time updates. |

## Limitations and next steps

- All data is synthetic; the model is not calibrated for real production traffic or loss economics.
- Shared infrastructure is evidence, not proof. Coverage of benign overlap remains limited.
- Attackers can reduce detectability through slower coordination, rotating infrastructure, or weaker transaction concentration.
- The in-memory live graph is appropriate for the prototype but would need persistent storage, incremental computation, access controls, monitoring, and load testing for production use.
- Future work includes broader hard-negative evaluation, calibrated cost-based thresholds, analyst-feedback capture, and independent evaluation on permitted real-world or public data.

---

Built for **Razorpay AI Buildathon 2026 — Track 02: AI Risk Manager**.
