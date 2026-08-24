# Engineering Decision Log — NexusGuard AI

This document records the architectural and modeling decisions made throughout the design and construction of NexusGuard AI, along with the engineering rationale for each choice.

---

### 1. Heterogeneous Graph Representation (Accounts, Devices, IPs)
- **Decision:** Model the payment ecosystem as a heterogeneous graph with typed nodes (`Account`, `Device`, `IP`) and derived `ACCOUNT_SHARES_IDENTIFIER_WITH_ACCOUNT` weighted projection edges.
- **Rationale:** Fraud rings operate across shared hardware and network infrastructure; modeling devices and IPs as first-class graph entities makes multi-hop transitively shared infrastructure directly discoverable via graph connectivity algorithms.

### 2. Exact IP ID vs Subnet Bucketing
- **Decision:** Restrict IP linkage to exact IP identifiers with carrier NAT / corporate proxy density caps (`MAX_ACCOUNTS_PER_IP = 20`), rather than raw `/16` subnet bucketing.
- **Rationale:** Subnet `/16` bucketing caused massive false-positive cascading where hundreds of innocent users sharing an ISP carrier block merged into giant single components. Exact IP matching with edge-weight decay (`0.6 / log2(n)`) isolates true collusion clusters while suppressing ISP noise.

### 3. Louvain Community Detection on Oversized Components
- **Decision:** Apply Louvain modularity-based community partitioning on components with $\ge 20$ accounts.
- **Rationale:** Prevents loosely connected benign components (e.g. university or office networks with accidental transitive overlap) from artificially merging into oversized fraud clusters.

### 4. XGBoost as Primary Supervised Model
- **Decision:** Deploy XGBoost (`XGBClassifier` with `scale_pos_weight`) as the primary supervised scoring model alongside Isolation Forest.
- **Rationale:** XGBoost captures non-linear, multi-feature interactions (e.g., synchronized creation window + elevated refund + shared device) that linear models miss, while `scale_pos_weight` natively handles severe class imbalance without synthetic label artifacts.

### 5. Retaining Isolation Forest as an Anomaly Signal
- **Decision:** Keep Isolation Forest trained exclusively on legitimate clusters rather than relying solely on supervised XGBoost.
- **Rationale:** Supervised models risk overfitting to known attack archetypes. Unsupervised Isolation Forest acts as a complementary zero-day detector for novel evasion patterns never seen during training.

### 6. Why No Graph Neural Network (GNN)
- **Decision:** Rely on explicit graph topology extraction (clustering coefficient, cycles, weighted degree, Louvain) fed into gradient boosting rather than end-to-end GNNs (GCN/GAT).
- **Rationale:** GNNs on dynamic graphs suffer from high inference latency, over-smoothing on bipartite-heavy topologies, and black-box unexplainability under regulatory review. Extracted graph features paired with XGBoost deliver sub-30ms inference with full feature-level auditability.

### 7. Hybrid Risk Engine (0.35 IF + 0.40 XGBoost + 0.25 Rules)
- **Decision:** Combine supervised XGBoost probability (40%), unsupervised IF anomaly score (35%), and structural rule signals (25%) into the final 0–100 risk score.
- **Rationale:** Ensures every alert is grounded in both statistical learning and deterministic structural evidence, establishing an interpretability floor where analysts can always audit $\ge 25\%$ of the score directly back to graph relationships.

### 8. Hard Negatives Architecture
- **Decision:** Explicitly synthesize 5 realistic benign overlap scenarios (family businesses sharing one device, corporate offices sharing an IP, households, high-volume merchants, elevated-refund apparel merchants).
- **Rationale:** Prevents naive single-signal false positives. Verifies that risk scores emerge exclusively from corroborating signal combinations rather than isolated shared infrastructure or high volume alone.

### 9. Single-Pipeline Real-Time Ingestion (PublicEvent Type Boundary)
- **Decision:** Enforce a strict `PublicEvent` type boundary where manual events and scenario simulator events enter through the exact same ingestion endpoint with no fraud labels.
- **Rationale:** Prevents test-label leakage and ensures the system operates strictly on raw telemetry available at transaction time, honoring the principle: *"Simulate the payments. Do not simulate the detection."*

### 10. WebSocket Streaming over Polling
- **Decision:** Implement native WebSocket streaming (`/api/ws`) for live event telemetry, latency breakdowns, and real-time risk deltas.
- **Rationale:** Eliminates polling overhead and provides an interactive, sub-50ms visual inspection interface for fraud operations teams and demo judges.
