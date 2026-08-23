# Coordinated Payment Abuse Detection
### Razorpay AI Buildathon — Track 02: AI Risk Manager

> **Thesis:** Individual transactions inside a fraud ring can look perfectly legitimate in isolation. The relationships between accounts, merchants, devices, and IPs — the *graph structure* — reveal coordinated abuse that per-transaction models cannot see.

---

## Detection Results (actual code execution, synthetic data)

All metrics below are from `python -m evaluation.evaluator` run against the same pipeline that powers the demo. No placeholder numbers.

| Metric | BL1: Txn-Only | BL2: Rule-Only | BL3: IF-Only | **Final: Hybrid** |
|--------|:---:|:---:|:---:|:---:|
| Precision | 76.4% | 81.8% | 14.6% | **75.4%** |
| Recall | 56.1% | 82.7% | 100% | **100%** |
| F1 Score | 64.7% | 82.2% | 25.4% | **86.0%** |
| FPR | 2.7% | 2.9% | 92.7% | **5.2%** |
| PR-AUC | 0.597 | 0.972 | 0.726 | **0.967** |

**Ring-level recall: 100% (19/19 fraud rings detected)**

| Ring Type | Detected | Total |
|-----------|:---:|:---:|
| Shared Device | 4 | 4 |
| Shared IP | 3 | 3 |
| Buyer-Merchant Collusion | 3 | 3 |
| Refund Farming | 3 | 3 |
| Circular Flow | 3 | 3 |
| Mixed Signal | 3 | 3 |

**Benign overlap (hard negatives) FPR:**
| Benign Type | FPR |
|-------------|:---:|
| Family Business | 0% |
| Household | 0% |
| High-Volume Merchant | 0% |
| Elevated Refund Merchant | 0% |
| Corporate Office | 12% (3/25) |

> **Disclaimer:** Dataset is 100% synthetic. Results demonstrate detection methodology. Not production-scale performance.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Detection Pipeline                          │
│                                                                 │
│  accounts.csv ──┐                                               │
│  devices.csv  ──┤   graph_builder.py   ┌─ feature_extractor.py │
│  ips.csv      ──┤──▶ Bipartite graph ──┤                        │
│  txns.csv     ──┤    (exact IDs +      │  18-feature vector:    │
│  acct_devs    ──┘    edge weights)     │  • Shared device score │
│  acct_ips     ──┘                      │  • Shared IP score     │
│                                        │  • Cycle detection     │
│                   Louvain community ───┤  • Creation sync ratio │
│                   detection            │  • Refund elevation    │
│                                        │  • Merchant conc.      │
│                                        └─ scorer.py             │
│                                                                 │
│   Isolation Forest (unsupervised, trained on legit clusters)   │
│   + Rule Score (weighted structural rules)                      │
│   Combined: 0.40 × IF + 0.60 × Rules → risk_score [0, 100]    │
│                                                                 │
│   Hard caps:                                                    │
│   • Loose large clusters (n>15, no cycle, low density) → ≤35   │
│   • Benign spread (accts created >1 day apart, small cluster)  │
│     → infrastructure signal reduced by 75%                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    evidence_builder.py
                              │
                     ┌────────────────┐
                     │  FastAPI v2.0  │  ← backend/api/
                     └────────────────┘
                              │
                    ┌──────────────────┐
                    │  React frontend  │  ← frontend/src/
                    │  (Vite + TSX)   │
                    └──────────────────┘
                    • Risk Overview
                    • Ring Investigation (graph viz + LLM analyst)
                    • Detection Metrics (4-baseline comparison)
```

### Graph Building
- Bipartite graph: accounts ↔ shared identifiers (devices, IPs)
- Exact IP IDs (not /16 subnets) prevent snowballing of legitimate accounts
- Edge weights: inverse of sharing count (device shared by 2 → weight=1.0; by 20 → weight=0.05)
- IP edges only created if shared by ≤20 accounts (hard cap prevents office subnets from creating edges)
- Louvain community detection on weighted subgraph (threshold=20)

### Scoring Logic
- **Rule Score** (0–1): structural signal combination weighted by fraud-specificity
  - Shared device concentration: 30% weight
  - Shared IP concentration: 15% weight
  - Cycle detection: 25% weight
  - Creation time synchronization (accounts created within 5 min): 10% weight
  - Refund elevation (>3× platform rate): 10% weight
  - Merchant concentration (>75% to single merchant): 10% weight
  - Multi-signal bonus: +5% per signal beyond 2 (max +15%)
  
- **IF Score** (0–1): IsolationForest trained on legitimate cluster feature vectors
  - Training: 30 real legit clusters + 400 synthetic (sizes 2–50, proper feature distributions)
  - Hard cap: clusters with n>15, no cycle, density<3%, no reciprocal txns → score ≤35 (below flag threshold)

- **Hybrid** = 0.40 × IF + 0.60 × Rule, flagged at ≥40

### Key Design Decisions
1. **Exact IP IDs**: Using exact IP identifiers (not /16 subnets) prevents transitive merging of office subnets into giant components.
2. **Dedicated identifiers for ring members**: `shared_device` ring members get dedicated IPs (not from the general pool), and `shared_ip` ring members get dedicated devices. This keeps their clusters tight and prevents merging with legitimate accounts.
3. **Creation-time spread modifier**: Accounts created >1 day apart with no cycles get 75% reduction in device/IP signal. Fraud rings batch-register within seconds; households share devices over months.
4. **Large sparse component cap**: A 30-account cluster with no cycle and low density is a transitive coincidence, not coordination — hard-capped below the flag threshold regardless of IF score.
5. **AI Investigator grounding**: LLM only sees structured evidence, never raw data. This prevents hallucination and enforces explainability.

---

## Setup

### Requirements
```
Python 3.9+  
Node.js 18+
```

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m data_gen.generator          # generate synthetic data (~5s)
python -m detection.pipeline          # run detection (~10s)
python -m evaluation.evaluator        # evaluate (~10s)
uvicorn api.main:app --reload         # start API on :8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                           # start dev server on :5173
```

### Quick Demo
Navigate to `http://localhost:5173` and:
1. **Risk Overview**: See all flagged rings sorted by risk score
2. **Click any Critical ring**: See graph visualization and 5 evidence items  
3. **Click "Investigate"**: AI analyst generates a structured write-up grounded in evidence
4. **Detection Metrics**: 4-baseline comparison table with actual numbers

---

## Project Structure
```
backend/
├── api/
│   ├── main.py              # FastAPI app, lifespan pipeline init
│   └── routers/
│       ├── rings.py         # /api/rings, /api/rings/hero
│       └── metrics.py       # /api/metrics/baselines, /benign-overlap
├── data_gen/
│   ├── config.py            # Dataset parameters, hard-negative counts
│   └── generator.py         # Synthetic data generator with ring injectors
├── detection/
│   ├── graph_builder.py     # Bipartite graph, exact IDs, edge weights
│   ├── feature_extractor.py # 18-feature cluster vector, Louvain
│   ├── scorer.py            # Hybrid IF+rule scoring, hard caps
│   ├── evidence_builder.py  # Human-readable evidence items
│   └── pipeline.py          # Orchestrates full detection pass
├── evaluation/
│   └── evaluator.py         # 4-baseline evaluation, PR-AUC, benign FPR
├── ml/
│   ├── train.py             # Train/val/test split by ring type
│   └── feature_ablation.py  # 5 ablation configs
└── llm/
    └── investigator.py      # Structured LLM investigation

frontend/
├── src/
│   ├── api/client.ts        # Typed API client
│   ├── screens/
│   │   ├── RiskOverview.tsx      # Sortable/filterable ring table
│   │   ├── RingInvestigation.tsx # Graph + evidence + LLM
│   │   └── DetectionMetrics.tsx  # 4-baseline comparison table
│   └── components/
│       ├── GraphCanvas.tsx   # D3 force graph
│       └── MetricCard.tsx    # Metric display card
```

---

*Built for Razorpay AI Buildathon — Track 02: AI Risk Manager*
