<div align="center">

# SANKET

### System for Analytics and Knowledge on Engineering Trajectories

**An AI-powered early-warning system for large public infrastructure projects.**

*Monitor the direction, not just the state.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-uvicorn-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LightGBM](https://img.shields.io/badge/Model-LightGBM%20%2B%20Isotonic-9ACD32)](https://lightgbm.readthedocs.io/)
[![Database](https://img.shields.io/badge/DB-SQLite%20%7C%20PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-106%20passing-brightgreen)](#-testing)
[![Deploy](https://img.shields.io/badge/deploy-Render-46E3B7)](https://render.com/)
[![Memory](https://img.shields.io/badge/peak%20memory-%3C512MB-orange)](#incremental-storage--io)

**PR-AUC 0.6467** · **ROC-AUC 0.7639** · **Brier 0.1824 (calibrated)** · **4.0-month median early warning**

</div>

---

## 📑 Table of Contents

| Section | What you'll find |
|---|---|
| [1. The Problem](#1--the-problem) | Why current-state monitoring fails |
| [2. The Core Idea](#2--the-core-idea) | Trajectory monitoring, with the math |
| [3. System Architecture](#3--system-architecture) | End-to-end component map |
| [4. Data Pipeline](#4--data-pipeline) | The 9 chronological stages |
| [5. Incrementality](#5--incrementality-the-engineering-core) | Chunked I/O and dependency propagation |
| [6. Dataset](#6--dataset) | Volumes, coverage, date range |
| [7. Data Quality & Identity](#7--project-identity--data-quality) | Canonicalization and sanitation |
| [8. Feature Catalog](#8--production-feature-catalog) | Every feature, defined |
| [9. Target Definition](#9--target-definition) | What "distress" means, formally |
| [10. Leakage Prevention](#10--leakage-prevention) | Point-in-time discipline |
| [11. Model & Validation](#11--machine-learning--validation) | Metrics, calibration, honesty |
| [12. Alert Thresholds](#12--alert-thresholds) | Risk tiers and operational burden |
| [13. Trajectory vs Current State](#13--trajectory-vs-current-state-monitoring) | The headline result |
| [14. Replay Engine](#14--replay-engine) | Auditable time travel |
| [15. Governance State Machine](#15--operational-governance) | From alert to recovery |
| [16. AI Explanation Layer](#16--ai-explanation-layer) | Gemini, strictly read-only |
| [17. API Reference](#17--api-reference) | All endpoints |
| [18. Database](#18--database) | Dual-mode storage |
| [19. Frontend](#19--frontend) | Zero-build dashboard |
| [20. Quickstart](#20--local-development-quickstart) | Run it in 4 commands |
| [21. Deployment](#21--deployment) | Render configuration |
| [22. Testing](#22--testing) | 106 tests, what they guard |
| [23. Security](#23--security) | Posture and limitations |
| [24. Limitations](#24--limitations) | What SANKET does *not* do |
| [25. Roadmap](#25--future-work) | Where this goes next |
| [26. FAQ](#26--faq) | Common questions |
| [27. Glossary](#27--glossary) | Every term, decoded |
| [28. Repository Structure](#28--repository-structure) | File-by-file map |

---

## 1. 🎯 The Problem

Traditionally, infrastructure governance relies on monitoring the **current state** of a project. However, by the time a project officially reports a "cost overrun" or a major "schedule delay," the technical or financial failure has already occurred on the ground months prior. Reporting is fundamentally **lagged by administrative approvals**.

Monitoring current state alone provides *reporting*, not *early warning*.

### The reporting lag, visualised

```mermaid
timeline
    title Why current-state monitoring is always late
    Month 0 : Real-world distress begins
            : Contractor slows, cash flow tightens
    Month 1-3 : Trajectory degrades
              : Expenditure velocity falls, drift accumulates
    Month 4-8 : Internal revision process
              : Cost revision proposals move through approvals
    Month 9-12 : Official record updated
               : Overrun finally appears in the flash report
    Response : Reactive only
             : Remediation options are now expensive and limited
```

The failure and the *record of* the failure are separated by months of administrative latency. A system that waits for the record is structurally incapable of prevention.

```mermaid
flowchart LR
    subgraph OLD["❌ Current-State Monitoring"]
        A1["Is cost revised?"] --> A2["Is schedule slipped?"]
        A2 --> A3["Flag AFTER the fact"]
    end
    subgraph NEW["✅ SANKET Trajectory Monitoring"]
        B1["How fast is spend moving?"] --> B2["Is that speed increasing<br/>or decaying?"]
        B2 --> B3["Flag BEFORE the record"]
    end
    OLD -.->|"median 2.0 months lead"| R["Audit Prioritization"]
    NEW -.->|"median 4.0 months lead"| R
```

---

## 2. 💡 The Core Idea

> **"Monitor the direction, not just the state."**

SANKET tracks the **longitudinal trajectory** of projects over time. By calculating the first and second derivatives — **velocity** and **acceleration** — of financial expenditure, physical progress, and schedule drift, SANKET detects deteriorating project momentum and predicts distress **3 to 11 months before** it is officially recorded as an overrun.

### The intuition

Two projects can report an *identical* state today and have completely different futures:

| | Project A | Project B |
|---|---|---|
| Expenditure today | 60% of baseline | 60% of baseline |
| Physical progress | 55% | 55% |
| **Velocity (last 3m)** | **+4.0 pts/month, steady** | **+0.4 pts/month, decaying** |
| **Acceleration** | **≈ 0 (healthy cruise)** | **strongly negative (stalling)** |
| Current-state verdict | Normal | Normal |
| **SANKET verdict** | **Normal** | **ESCALATE** |

*(Illustrative comparison to explain the mechanism.)*

State monitoring cannot distinguish these two. Derivative monitoring can.

### The math

For a metric $M$ observed at monthly timestamps $t$:

**First derivative — velocity (momentum):**

$$V^{1m}_{M}(t) = M(t) - M(t-1)$$

$$V^{3m}_{M}(t) = \frac{M(t) - M(t-3)}{3}$$

**Second derivative — acceleration (change in momentum):**

$$A_{M}(t) = V^{1m}_{M}(t) - V^{1m}_{M}(t-1)$$

**Exponentially weighted momentum**, which favours recent months while retaining history:

$$\text{EWMA}_V(t) = \alpha \cdot V^{1m}(t) + (1-\alpha)\cdot \text{EWMA}_V(t-1)$$

**Peer-relative normalization**, so a project is judged against comparable projects rather than an absolute constant:

$$Z^{\text{peer}}_{V_{fin}}(t) = \frac{V_{fin}(t) - \mu_{\text{cohort}}(t)}{\sigma_{\text{cohort}}(t)}$$

where the cohort is defined by `(reporting_month, sector_clean, scale_bucket)` and statistics are computed **purely on trailing data**.

> **Why the second derivative matters:** a project with falling but *stabilising* velocity is recovering. A project with falling and *further decelerating* velocity is failing. Only $A$ separates the two.

---

## 3. 🏗️ System Architecture

The macro flow of the system:

```
Project Data → Canonicalization → Timeline Construction → Trajectory Features
    → Risk Prediction → Risk Tier → Governance/Recovery → Authority Escalation
```

> **Scope note:** SANKET provides early-warning **predictive alerts** to optimize audit and review prioritization. The ML model does **not** automatically issue legal/regulatory penalties or determine contractor liability.

### Full component map

```mermaid
graph TD
    A[PDF Flash Reports] --> B(Extraction Engine)
    B --> C(Content-Addressed Manifest)
    C --> D[(Canonical CSV Datasets)]
    D --> E(Timeline Builder)
    E --> F(Trajectory & Target Generator)
    F --> G(Feature Store - Parquet)
    G --> H[Frozen LightGBM Model]
    H --> I[(SQLite / PostgreSQL)]
    I --> J[FastAPI Backend]
    J --> K[Vanilla JS Frontend]
    J -.-> L[Gemini AI Explanations]
```

### Layered view

```mermaid
graph TB
    subgraph L1["🗄️ Ingestion Layer"]
        I1["Raw PDF flash reports"]
        I2["Optical table extraction"]
        I3["ingestion_manifest.json<br/>content-addressed hashes"]
    end
    subgraph L2["🧹 Canonical Layer"]
        C1["Deduplication"]
        C2["Identity resolution"]
        C3["Rule-based cleaning"]
    end
    subgraph L3["📈 Temporal Layer"]
        T1["Monthly timeline per project"]
        T2["Velocity / Acceleration / EWMA"]
        T3["Point-in-time target labels"]
    end
    subgraph L4["🤖 Inference Layer"]
        M1["Feature matrix - Parquet"]
        M2["Frozen LightGBM + Isotonic"]
        M3["Calibrated probability → risk tier"]
    end
    subgraph L5["⚖️ Governance Layer"]
        G1["State machine"]
        G2["Replay engine"]
        G3["Gemini explanations - read only"]
    end
    L1 --> L2 --> L3 --> L4 --> L5
```

### Design principles

| Principle | How it is enforced |
|---|---|
| **Extraction ≠ Engineering** | The pipeline strictly separates optical extraction from downstream temporal engineering, so a parser bug never silently contaminates features. |
| **Point-in-time or nothing** | Every feature is engineered strictly from data available at or before the prediction month $t$. |
| **Idempotency** | Content-addressed manifests mean re-running the pipeline on unchanged input is a no-op. |
| **Bounded memory** | Chunk-by-chunk and partition-by-partition updates keep peak memory strictly under 512MB. |
| **Frozen artifacts** | The production model is a versioned file, not a moving target. |
| **Honest nulls** | Unknown futures are `NaN` and dropped — never imputed as zero. |

---

## 4. 🔄 Data Pipeline

The data pipeline strictly separates extraction from downstream temporal engineering.

```mermaid
flowchart LR
    S1["1️⃣ NEW PDF"] --> S2["2️⃣ MANIFEST"]
    S2 --> S3["3️⃣ EXTRACTION"]
    S3 --> S4["4️⃣ CANONICAL"]
    S4 --> S5["5️⃣ TIMELINE"]
    S5 --> S6["6️⃣ TRAJECTORY"]
    S6 --> S7["7️⃣ TARGET"]
    S7 --> S8["8️⃣ FEATURES"]
    S8 --> S9["9️⃣ PORTFOLIO"]
```

### Stage-by-stage

| # | Stage | What happens | Why it exists |
|---|---|---|---|
| 1 | **NEW PDF** | Raw project monitoring reports arrive. | Source of truth is the official administrative record. |
| 2 | **MANIFEST** | Content-addressed idempotent tracking of parsed files. | Lets the system know *exactly* what changed, by hash rather than by filename or timestamp. |
| 3 | **EXTRACTION** | Optical extraction of tables to raw observations. | Converts unstructured PDF tables into row-level records. |
| 4 | **CANONICAL** | Deduplication and rule-based cleaning. | One project-month, one truth. |
| 5 | **TIMELINE** | Assembling longitudinal monthly timeseries per project. | Turns rows into a trajectory. This is where a "project" becomes a *curve*. |
| 6 | **TRAJECTORY** | Computing rolling velocities and accelerations. | The derivative layer — the intellectual core of SANKET. |
| 7 | **TARGET** | Point-in-time calculation of forward-looking distress. | Labels each observation with what happened over the *next* 12 months. |
| 8 | **FEATURES** | Constructing the final ML inference matrix. | Assembles the exact column set the frozen model expects. |
| 9 | **PORTFOLIO** | Batch updating the current active risk predictions. | Refreshes the live dashboard view of the portfolio. |

### Where each stage writes

```mermaid
flowchart TD
    P1["DATA(RAW)/*.pdf"] --> P2["ingestion_manifest.json"]
    P2 --> P3["raw observations"]
    P3 --> P4["project_monthly.csv<br/>(canonical)"]
    P4 --> P5["timeline partitions"]
    P5 --> P6["feature store (Parquet)"]
    P6 --> P7["predictions → SQLite / PostgreSQL"]
    P7 --> P8["FastAPI → Dashboard"]
```

---

## 5. ⚡ Incrementality: the engineering core

### Incremental Storage / I/O

The pipeline is **fully incremental in both mathematical compute and I/O**.

Using `ingestion_manifest.json`, SANKET:

1. Detects exactly which PDFs changed (by content hash, not mtime).
2. Isolates the affected `(project, month)` pairs.
3. Propagates the **minimal required changes** through the pipeline.

Large datasets — for example `project_monthly.csv` and the timeline partitions — are updated **chunk-by-chunk and partition-by-partition**, keeping peak memory strictly under **512MB** for horizontal scalability on micro-instances.

```mermaid
flowchart TD
    A["New / edited PDF detected<br/>via content hash"] --> B{"Hash changed?"}
    B -->|No| Z["No-op ✅<br/>idempotent skip"]
    B -->|Yes| C["Identify affected<br/>(project, month) pairs"]
    C --> D["Rewrite only affected<br/>canonical chunks"]
    D --> E["Rebuild only affected<br/>timeline partitions"]
    E --> F["Recompute trajectories<br/>in the affected window"]
    F --> G{"Do peer cohorts<br/>shift?"}
    G -->|Yes| H["Backfill peer normalization<br/>for the whole cohort"]
    G -->|No| I["Skip peer backfill"]
    H --> J["Regenerate features → predict"]
    I --> J
    J --> K["Update portfolio risk table"]
```

### Data Dependency Propagation

This is the subtle part, and the reason naive incremental pipelines are wrong.

Because some features — notably `Z_peer_V_fin` — are **normalized against peer cohorts** sharing the same `(reporting_month, sector_clean, scale_bucket)`, editing a *single* project changes the **mean and standard deviation** of that cohort. Every peer's normalized feature is now stale.

SANKET's incremental pipeline correctly identifies when an edit to a single project **cascades to alter the normalization denominators of its peers**, and gracefully backfills the affected peer trajectories.

```mermaid
graph TD
    X["✏️ Edit: Project P, month M"] --> Y["Cohort C = (M, sector, scale_bucket)"]
    Y --> Z1["μ of C changes"]
    Y --> Z2["σ of C changes"]
    Z1 --> W["Every peer's Z_peer_V_fin<br/>in cohort C is now stale"]
    Z2 --> W
    W --> V["Backfill all peers in C<br/>— not just P"]
```

> **Why this matters:** an incremental pipeline that only recomputes the edited project would silently serve stale, subtly-wrong features for every peer in the cohort. Correct incrementality is a *correctness* property, not just a speed optimisation.

---

## 6. 📊 Dataset

*(Verified current baseline)*

| Metric | Value |
|---|---|
| Tracked PDF reports | **354** |
| Raw extraction records | **1,118,502** |
| Canonical project-month records | **478,356** |
| Archive entities | **125,124** |
| **Active modeling projects** | **9,907** |
| Date range | **2001-10 → 2026-07** |

> **Note:** Archive entities include historical variations and minor name changes. The active modeling dataset comprises **9,907 eligible genuine unique projects**.

### From raw rows to modelled projects

```mermaid
flowchart LR
    A["1,118,502<br/>raw extraction records"] -->|dedupe + clean| B["478,356<br/>canonical project-months"]
    B -->|identity resolution| C["125,124<br/>archive entities"]
    C -->|eligibility filter| D["9,907<br/>genuine unique projects"]
    D -->|walk-forward split| E["56,514<br/>OOF test observations"]
```

The ~24 years of coverage is what makes trajectory modelling possible at all — derivatives need history, and forward-looking targets need a future to look at.

---

## 7. 🧼 Project Identity / Data Quality

Raw records undergo extensive sanitation:

- **Identity canonicalization** — project identities are canonicalized based on similarity heuristics and **PAIMANA official identifiers** where available.
- **Conflict reconciliation** — conflicting duplicate observations for the same `(project_id, reporting_month)` are reconciled via **max-conservative merging**.
- **Artifact filtering** — synthetic/front-matter artifacts (e.g. a table of contents misidentified as a project) are filtered out.
- **Right-censoring discipline** — observations where the future is unknown are strictly marked as `NaN` and dropped from training, **never assumed to be zero**.

```mermaid
flowchart TD
    R["Raw extracted rows"] --> A["Strip front-matter /<br/>TOC artifacts"]
    A --> B["Resolve identity<br/>PAIMANA ID → similarity heuristics"]
    B --> C{"Duplicate<br/>(project_id, month)?"}
    C -->|Yes| D["Max-conservative merge"]
    C -->|No| E["Pass through"]
    D --> F["Canonical record"]
    E --> F
    F --> G{"Future window<br/>complete?"}
    G -->|No| H["Mark NaN → drop from training"]
    G -->|Yes| I["Eligible for labelling"]
```

> **On "max-conservative merging":** when two sources disagree about the same project-month, SANKET resolves toward the interpretation that does not understate risk. Silence is never read as good news.

---

## 8. 🧮 Production Feature Catalog

Features are engineered **strictly from data available at or before the prediction month $t$**.

### Financial trajectory

| Feature | Meaning |
|---|---|
| `V_fin_1m` | 1-month financial velocity — short-run momentum of financial progress |
| `V_fin_3m` | 3-month financial velocity — smoothed momentum, less sensitive to reporting noise |
| `A_fin` | Financial acceleration — is momentum building or decaying? |
| `EWMA_V_fin` | Exponentially weighted financial velocity — recency-weighted trend |

### Expenditure trajectory

| Feature | Meaning |
|---|---|
| `V_exp_1m` | 1-month expenditure velocity — short-run burn rate change |
| `V_exp_3m` | 3-month expenditure velocity — smoothed burn rate |
| `A_exp` | Expenditure acceleration — burn rate stalling or surging |

### Cost / schedule

| Feature | Meaning |
|---|---|
| `cost_revision_ratio` | Revised cost relative to the original baseline |
| `expenditure_to_baseline` | Cumulative expenditure against the baseline cost |
| `schedule_deviation_months` | Officially recorded deviation from the sanctioned schedule |
| `schedule_deviation_change` | Month-over-month change in that deviation — schedule *velocity* |
| `completion_date_drift` | Movement of the anticipated completion date |

### Peer / context

| Feature | Meaning |
|---|---|
| `Z_peer_V_fin` | Financial velocity normalized against a trailing peer cohort |
| `sector_clean` | Canonicalized sector label |
| `scale_bucket` | Project size band, used for fair peer comparison |

### Trajectory & physical

| Feature | Meaning |
|---|---|
| `trajectory_risk_score` | Composite trajectory-health signal |
| `V_phys_1m` | 1-month physical progress velocity |
| `V_phys_3m` | 3-month physical progress velocity |
| `A_phys` | Physical progress acceleration |
| `financial_physical_gap` | Divergence between money spent and work done — a classic distress signature |

### Temporal / history

| Feature | Meaning |
|---|---|
| `project_age_months` | Months since project inception |
| `observation_number` | Index of this observation in the project's timeline |
| `months_since_previous_observation` | Gap since the last report |
| `reporting_gap_flag` | Flags irregular reporting — *silence is itself a signal* |

### Baseline

| Feature | Meaning |
|---|---|
| `C_base` | Baseline sanctioned cost — scale anchor for all ratios |

### Feature families at a glance

```mermaid
mindmap
  root((SANKET Features))
    Financial
      V_fin_1m
      V_fin_3m
      A_fin
      EWMA_V_fin
    Expenditure
      V_exp_1m
      V_exp_3m
      A_exp
    Cost and Schedule
      cost_revision_ratio
      expenditure_to_baseline
      schedule_deviation_months
      schedule_deviation_change
      completion_date_drift
    Peer Context
      Z_peer_V_fin
      sector_clean
      scale_bucket
    Trajectory and Physical
      trajectory_risk_score
      V_phys_1m
      V_phys_3m
      A_phys
      financial_physical_gap
    Temporal
      project_age_months
      observation_number
      months_since_previous_observation
      reporting_gap_flag
    Baseline
      C_base
```

> **`financial_physical_gap` deserves special attention.** When money is leaving the account faster than concrete is being poured, the project is consuming budget without converting it into progress. That gap, tracked over time, is one of the most interpretable distress signatures in the feature set.

---

## 9. 🎯 Target Definition

SANKET predicts a **12-month forward horizon**.

**Primary target:** `overrun_composite_12m`

This is a logical **OR** between two conditions:

| Component | Condition |
|---|---|
| `cost_overrun_12m` | A **≥ 5%** increase in the revised cost baseline within 12 months |
| `schedule_overrun_12m` | A **≥ 6.0 month** forward drift in the anticipated completion date or official schedule deviation within 12 months |

$$\texttt{overrun\_composite\_12m}(t) = \texttt{cost\_overrun\_12m}(t) \; \lor \; \texttt{schedule\_overrun\_12m}(t)$$

Incomplete future windows — **right censoring** — are **excluded, not imputed as negative**.

```mermaid
flowchart TD
    T["Observation at month t"] --> W["Look forward: t+1 … t+12"]
    W --> C1{"Revised cost baseline<br/>increases ≥ 5%?"}
    W --> C2{"Completion date or schedule<br/>deviation drifts ≥ 6.0 months?"}
    C1 -->|Yes| POS["Label = 1 (distress)"]
    C2 -->|Yes| POS
    C1 -->|No| CHK
    C2 -->|No| CHK
    CHK{"Is the full 12-month<br/>window observable?"}
    CHK -->|Yes| NEG["Label = 0 (healthy)"]
    CHK -->|No| DROP["❌ Right-censored<br/>→ NaN, dropped from training"]
```

> **Why censoring discipline matters:** if you label an unobservable future as "no overrun," you teach the model that recent months are systematically safe. That single shortcut would poison every prediction about the present — which is precisely the period you care about. SANKET refuses to do this.

---

## 10. 🔒 Leakage Prevention

SANKET strictly adheres to point-in-time constraints:

- Evaluated via **strict chronological walk-forward validation** with a **12-month forward horizon safety buffer**, enforcing $\max(\text{train}) < \min(\text{test})$.
- **Replay engines** simulate historical environments without future knowledge.
- **Peer statistics** (`Z_peer_V_fin`) are computed purely on **trailing cohorts**.

```mermaid
gantt
    title Chronological walk-forward validation with horizon buffer
    dateFormat YYYY-MM
    axisFormat %Y
    section Fold 1
    Train           :a1, 2001-10, 2012-12
    Horizon buffer  :crit, a2, 2013-01, 2013-12
    Test            :a3, 2014-01, 2015-12
    section Fold 2
    Train           :b1, 2001-10, 2016-12
    Horizon buffer  :crit, b2, 2017-01, 2017-12
    Test            :b3, 2018-01, 2019-12
    section Fold 3
    Train           :c1, 2001-10, 2020-12
    Horizon buffer  :crit, c2, 2021-01, 2021-12
    Test            :c3, 2022-01, 2023-12
```

*(Fold boundaries shown are schematic — the enforced invariants are chronological ordering and the 12-month buffer.)*

### The three leakage traps, and how each is closed

| Trap | How it leaks | SANKET's defence |
|---|---|---|
| **Random splits** | A test row's future sits in the training set. | Strict chronological walk-forward only. |
| **Horizon bleed** | Training rows whose 12-month label window overlaps the test period. | Explicit 12-month forward-horizon safety buffer between train and test. |
| **Peer leakage** | Cohort $\mu$ / $\sigma$ computed over the full dataset, including the future. | Peer statistics computed purely on trailing cohorts. |

> A model that leaks will look excellent and behave uselessly. The buffer costs accuracy on paper and buys trust in production.

---

## 11. 🤖 Machine Learning & Validation

The production model is a **LightGBM Classifier** with **Isotonic Calibration**.

It operates as a **frozen production artifact** (`vigil_production_model.joblib`) and is **not** automatically retrained during standard monthly incremental ingestion.

```mermaid
flowchart LR
    F["Feature matrix<br/>(point-in-time)"] --> L["LightGBM Classifier<br/>gradient-boosted trees"]
    L --> R["Raw score"]
    R --> I["Isotonic Calibration"]
    I --> P["Calibrated probability<br/>p ∈ [0,1]"]
    P --> T["Risk tier mapping"]
    L -.-> S["TreeSHAP<br/>feature attributions"]
    S -.-> X["AI explanation layer"]
```

### Why these choices

| Choice | Rationale |
|---|---|
| **LightGBM** | Handles heterogeneous tabular features, missing values, and non-linear interactions natively — a good match for sparse administrative data. |
| **Isotonic calibration** | Converts scores into *probabilities you can threshold*. Governance tiers are only meaningful if 0.50 genuinely means 0.50. |
| **Frozen artifact** | Predictions are reproducible and auditable. An alert issued last month can be reproduced exactly this month. |
| **TreeSHAP** | Every alert carries a per-feature attribution, so no alert is a black box. |

### Verified Out-of-Fold (OOF) metrics

*N = 56,514 test observations across 9,907 projects*

| Metric | Value | Interpretation |
|---|---|---|
| **PR-AUC (Global OOF)** | **0.6467** | Precision-recall area — the right metric for imbalanced distress detection |
| **ROC-AUC (Global OOF)** | **0.7639** | Ranking quality across all thresholds |
| **Brier Score (uncalibrated)** | 0.1926 | Mean squared error of the probability itself |
| **Brier Score (isotonic calibrated)** | **0.1824** | Lower is better — calibration measurably improves probability quality |

> **Note:** Validation metrics represent **historical evaluation** and are **not guarantees of future performance**.

### Calibration effect

```mermaid
flowchart LR
    A["Brier 0.1926<br/>uncalibrated"] -->|isotonic calibration| B["Brier 0.1824<br/>calibrated ✅"]
```

The improvement is what licenses the use of fixed numeric thresholds for governance tiers. Without calibration, "0.50" would be an arbitrary cut on an arbitrary score.

---

## 12. 🚦 Alert Thresholds

The calibrated model probabilities map to specific operational governance tiers:

| Tier | Threshold | Operational meaning |
|:---|:---|:---|
| 🟢 **NORMAL** | `< 0.40` | No action required |
| 🟡 **WATCH** | `≥ 0.40` | Broad surveillance |
| 🟠 **REVIEW** | `≥ 0.45` | Prioritized PMU scrutiny |
| 🔴 **ESCALATE** | `≥ 0.50` | High-confidence Minister / Authority review |

```mermaid
flowchart LR
    P["Calibrated probability p"] --> D1{"p ≥ 0.50?"}
    D1 -->|Yes| E["🔴 ESCALATE<br/>Authority review"]
    D1 -->|No| D2{"p ≥ 0.45?"}
    D2 -->|Yes| R["🟠 REVIEW<br/>PMU scrutiny"]
    D2 -->|No| D3{"p ≥ 0.40?"}
    D3 -->|Yes| W["🟡 WATCH<br/>Surveillance"]
    D3 -->|No| N["🟢 NORMAL"]
```

> These are **risk identification tiers**. Business logic — **not** the ML model — governs statutory transitions or official project recovery tracking.

The tiers are deliberately close together (0.40 / 0.45 / 0.50) because they encode **escalating institutional cost**, not escalating certainty. Surveillance is cheap; a ministerial review is not. The threshold spacing is an operational-burden decision.

---

## 13. 📈 Trajectory vs Current-State Monitoring

This is the central empirical result of the project.

At a **matched operational alert burden** — identifying ~**8% of the portfolio** for audit — the trajectory features provide:

| Approach | Median early warning | False-alert rate |
|---|---|---|
| Current-state static heuristics | **2.0 months** | — |
| **SANKET trajectory features** | **4.0 months** | **2.38%** (at threshold = 0.50) |

```mermaid
flowchart LR
    subgraph B["Median early-warning lead time"]
        direction TB
        CS["Current-state heuristics<br/>▓▓ 2.0 months"]
        TR["SANKET trajectory<br/>▓▓▓▓ 4.0 months"]
    end
```

**Why "matched alert burden" is the honest comparison:** any model can buy more lead time by flagging more projects. Holding the audit burden fixed at ~8% of the portfolio means the extra two months of warning come from *better signal*, not from *more alarms*. The 2.38% false-alert rate at threshold 0.50 is what keeps the system usable by a real oversight team rather than ignorable.

Across the observed range, SANKET detects distress **3 to 11 months** before it is officially recorded as an overrun.

---

## 14. ⏪ Replay Engine

SANKET includes a **Point-in-Time replay engine** that allows auditors to "time travel" to any historical month, feed the **exact information available at that time** into the model, and simulate the generated risk alerts alongside the **actual real-world outcome** — providing transparent validation of the model's predictive lead time.

```mermaid
sequenceDiagram
    participant A as Auditor
    participant UI as Replay UI
    participant API as FastAPI
    participant TS as Timeline Store
    participant M as Frozen Model

    A->>UI: "Show me Project X as of 2019-04"
    UI->>API: GET /api/projects/{id}/replay
    API->>TS: Fetch observations WHERE month <= 2019-04
    Note over TS: Strictly no future rows
    TS-->>API: Point-in-time feature vector
    API->>M: Predict with frozen artifact
    M-->>API: Calibrated probability + tier
    API-->>UI: Simulated alert for 2019-04
    UI->>A: Alert shown beside the real outcome
    Note over A: Lead time is directly observable
```

### Why the replay engine is the trust layer

An oversight body cannot act on a model it cannot interrogate. The replay engine answers the only question that actually matters to an auditor:

> *"If this system had been running in April 2019, would it have warned us — and how early?"*

Because the model is a **frozen artifact** and the timeline store is strictly point-in-time, that question has a reproducible answer rather than a persuasive one.

---

## 15. ⚖️ Operational Governance

Projects flagged by the SANKET engine enter an operational state machine tracked in the database.

**Recovery path:**

```
NORMAL → WATCH → CONTRACTOR_WARNING → RESPONSE_SUBMITTED → UNDER_RECOVERY → RECOVERED
```

**Persistent deterioration path:**

```
UNDER_RECOVERY → PERSISTENT_DETERIORATION → AUTHORITY_ESCALATION
```

```mermaid
stateDiagram-v2
    [*] --> NORMAL
    NORMAL --> WATCH: risk tier rises
    WATCH --> CONTRACTOR_WARNING: sustained deterioration
    CONTRACTOR_WARNING --> RESPONSE_SUBMITTED: contractor responds
    RESPONSE_SUBMITTED --> UNDER_RECOVERY: remediation begins
    UNDER_RECOVERY --> RECOVERED: trajectory improves
    UNDER_RECOVERY --> PERSISTENT_DETERIORATION: trajectory keeps degrading
    PERSISTENT_DETERIORATION --> AUTHORITY_ESCALATION: escalate to authority
    RECOVERED --> [*]
    AUTHORITY_ESCALATION --> [*]
```

| State | Meaning |
|---|---|
| `NORMAL` | No active concern |
| `WATCH` | Under broad surveillance |
| `CONTRACTOR_WARNING` | Formal warning issued |
| `RESPONSE_SUBMITTED` | Contractor has responded |
| `UNDER_RECOVERY` | Active remediation in progress |
| `RECOVERED` | Trajectory restored; case closed |
| `PERSISTENT_DETERIORATION` | Remediation has failed to arrest decline |
| `AUTHORITY_ESCALATION` | Escalated to higher authority |

> **Separation of concerns:** the ML model produces a *probability*. The state machine produces *institutional action*. Keeping them apart is what stops a statistical artefact from turning into a statutory consequence.

---

## 16. 🧠 AI Explanation Layer

SANKET integrates the **Gemini 1.5 Flash** API (`@google/genai` SDK) to translate complex **TreeSHAP feature importances** and raw trajectory data into **natural language project briefs** and **conversational Q&A**.

The AI serves strictly as an **explanatory assistant** and is **read-only** — it does **not** alter the risk probability, issue alerts, or modify project states.

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Database
    participant G as Gemini 1.5 Flash

    U->>FE: "Why is this project flagged?"
    FE->>API: POST /api/ai/project-brief
    API->>DB: Fetch prediction + trajectory + TreeSHAP values
    DB-->>API: Structured evidence
    API->>G: Prompt with structured evidence only
    G-->>API: Natural-language brief
    API-->>FE: Explanation text
    FE->>U: Readable project brief
    Note over G,DB: ❌ Gemini never writes to the DB<br/>❌ Never changes probability or tier
```

### The read-only boundary

```mermaid
flowchart LR
    subgraph AUTH["✅ Authoritative — deterministic"]
        M["LightGBM probability"]
        T["Risk tier"]
        S["Governance state"]
    end
    subgraph EXPL["💬 Explanatory — generative"]
        B["Project briefs"]
        Q["Conversational Q&A"]
    end
    AUTH -->|"read only"| EXPL
    EXPL -.->|"❌ no write path"| AUTH
```

This boundary is deliberate. The numbers that drive governance action are produced by a frozen, calibrated, auditable model. The language that *describes* those numbers is generative. A reader can dispute the wording without ever destabilising the decision.

---

## 17. 🔌 API Reference

The backend is built on **FastAPI** (`uvicorn`).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service status |
| `GET` | `/api/projects` | List all tracked projects |
| `GET` | `/api/projects/{id}` | Fetch project details and latest predictions |
| `GET` | `/api/projects/{id}/timeline` | Fetch full longitudinal history |
| `GET` | `/api/projects/{id}/replay` | Simulate historical point-in-time predictions |
| `GET` | `/api/dashboard/summary` | Aggregate portfolio risk stats |
| `POST` | `/api/monitor/projects` | Register a project for active governance |
| `POST` | `/api/ai/project-brief` | Generate a Gemini-powered summary report |
| `POST` | `/api/assistant` | Conversational query over project state |

### Endpoints by concern

```mermaid
flowchart TD
    API["FastAPI application<br/>sanket/api.py"]
    API --> H["Ops<br/>/health"]
    API --> P["Projects<br/>/api/projects<br/>/api/projects/{id}<br/>/api/projects/{id}/timeline"]
    API --> R["Audit<br/>/api/projects/{id}/replay"]
    API --> D["Portfolio<br/>/api/dashboard/summary"]
    API --> G["Governance<br/>POST /api/monitor/projects"]
    API --> AI["AI layer<br/>POST /api/ai/project-brief<br/>POST /api/assistant"]
```

### Example calls

```bash
# Service health
curl http://localhost:8000/health

# Portfolio-level risk summary
curl http://localhost:8000/api/dashboard/summary

# Full longitudinal history for a project
curl http://localhost:8000/api/projects/PROJECT_ID/timeline

# Point-in-time replay
curl "http://localhost:8000/api/projects/PROJECT_ID/replay"

# Register a project for active governance tracking
curl -X POST http://localhost:8000/api/monitor/projects \
  -H "Content-Type: application/json" \
  -d '{"project_id": "PROJECT_ID"}'

# Generate an AI project brief
curl -X POST http://localhost:8000/api/ai/project-brief \
  -H "Content-Type: application/json" \
  -d '{"project_id": "PROJECT_ID"}'
```

> Request and response shapes above are illustrative. Interactive, always-accurate schemas are served by FastAPI itself at **`/docs`** (Swagger UI) and **`/redoc`** once the server is running.

---

## 18. 🗄️ Database

SANKET supports **dual database modes** via connection pooling:

| Mode | When it's used | Location |
|---|---|---|
| **SQLite (WAL mode)** | Default zero-config storage for local development | `DATA/monitoring.db` |
| **PostgreSQL** | Production deployment using `psycopg2` | Provided via `DATABASE_URL` |

```mermaid
flowchart TD
    A["sanket/db.py<br/>connection pool"] --> B{"DATABASE_URL set?"}
    B -->|Yes| C["PostgreSQL via psycopg2<br/>production"]
    B -->|No| D["SQLite in WAL mode<br/>DATA/monitoring.db"]
    C --> E["Parameterized queries<br/>%s placeholders"]
    D --> F["Parameterized queries<br/>? bindings"]
```

**WAL mode** matters for local development: it allows the API to read while the pipeline writes, so a dashboard refresh during ingestion does not block or corrupt.

### What the database holds, conceptually

```mermaid
erDiagram
    PROJECT ||--o{ OBSERVATION : "has monthly"
    PROJECT ||--o{ PREDICTION : "receives"
    PROJECT ||--o| GOVERNANCE_STATE : "currently in"
    OBSERVATION }o--|| PREDICTION : "scored at month t"
```

*(Conceptual entity view for orientation — see `sanket/db.py` for the authoritative schema.)*

---

## 19. 🖥️ Frontend

The frontend is a lightweight **Vanilla JS** application — `HTML`, `CSS`, and `JS` — utilizing **Tailwind-style utilities**. It requires **no Node.js build step** for core execution.

It includes:

- 📊 Interactive charts of financial, physical, and schedule trajectories
- ⏪ A replay UI for point-in-time auditing
- ⚖️ Governance intervention tracking
- 🧠 AI explanation panels

```mermaid
flowchart LR
    U["Auditor / PMU officer"] --> UI["Vanilla JS dashboard"]
    UI --> C1["Portfolio risk overview"]
    UI --> C2["Project trajectory charts"]
    UI --> C3["Replay timeline"]
    UI --> C4["Governance actions"]
    UI --> C5["AI brief panel"]
    C1 & C2 & C3 & C4 & C5 --> API["FastAPI"]
```

> **Why zero-build:** a government oversight tool that needs a Node toolchain to render is a tool that will not be deployed. Opening `frontend/public/index.html` is a deliberate deployment feature, not a shortcut.

---

## 20. 🚀 Local Development Quickstart

```bash
# 1. Clone & environment setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the Incremental Pipeline
python3 run_incremental_pipeline.py

# 3. Start the API server
uvicorn sanket.api:app --reload

# 4. Access the Frontend
open frontend/public/index.html
```

### Environment variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://user:pass@host/dbname  # Optional: defaults to local SQLite if omitted
SANKET_STORAGE_MODE=local
```

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | For the AI layer | Enables Gemini-powered briefs and Q&A |
| `DATABASE_URL` | Optional | Switches to PostgreSQL; defaults to local SQLite if omitted |
| `SANKET_STORAGE_MODE` | Yes | Selects storage mode (`local` for development) |

### First-run flow

```mermaid
flowchart LR
    A["venv + pip install"] --> B["run_incremental_pipeline.py"]
    B --> C["DATA/monitoring.db populated"]
    C --> D["uvicorn sanket.api:app --reload"]
    D --> E["open frontend/public/index.html"]
```

---

## 21. ☁️ Deployment

SANKET is fully configured for deployment on **Render** via `render.yaml`.

| Setting | Value |
|---|---|
| **Build command** | `pip install -r requirements.txt` |
| **Start command** | `uvicorn sanket.api:app --host 0.0.0.0 --port $PORT` |
| **Port** | Managed via the `$PORT` environment variable |

```mermaid
flowchart LR
    G["Git push"] --> R["Render build<br/>pip install -r requirements.txt"]
    R --> S["uvicorn sanket.api:app<br/>--host 0.0.0.0 --port $PORT"]
    S --> DB{"DATABASE_URL<br/>provided?"}
    DB -->|Yes| PG["PostgreSQL"]
    DB -->|No| SL["SQLite fallback"]
```

The sub-512MB memory ceiling is what makes deployment on a micro-instance viable — the pipeline never loads a full dataset into memory, so the hosting tier is determined by traffic, not by data volume.

---

## 22. 🧪 Testing

Run the test suite — **106 tests** covering model leakage, idempotency, incremental parity, API, and target definitions:

```bash
python3 -m pytest tests/
```

| Test family | What it guards against |
|---|---|
| **Model leakage** | Any future information reaching a point-in-time feature |
| **Idempotency** | Re-running the pipeline on unchanged input changing the output |
| **Incremental parity** | Incremental runs diverging from a full rebuild — *the single most important invariant in the system* |
| **API** | Endpoint contract regressions |
| **Target definitions** | Drift in the 5% / 6.0-month thresholds or censoring rules |

```mermaid
flowchart TD
    T["pytest tests/ — 106 tests"] --> A["Leakage invariants"]
    T --> B["Idempotency"]
    T --> C["Incremental == Full rebuild"]
    T --> D["API contracts"]
    T --> E["Target definition"]
```

> **Incremental parity is the load-bearing test.** An incremental pipeline is only trustworthy if it provably produces byte-equivalent results to a full rebuild. Without that test, every speed gain is a correctness risk.

---

## 23. 🔐 Security

- **CORS** is strictly configured in FastAPI.
- **Secrets** — keys such as `GEMINI_API_KEY` are required via environment variables and never committed.
- **SQL injection** — all SQL operations use parameterized queries (`psycopg2` placeholders and SQLite `?` bindings).
- **(Limitation)** SANKET currently does **not** implement user authentication / authorization; it is designed to run in a **protected VPC / intranet environment**.

```mermaid
flowchart TD
    A["Request"] --> B["CORS policy"]
    B --> C["FastAPI route"]
    C --> D["Parameterized query layer"]
    D --> E["Database"]
    F["Environment variables"] -.->|secrets injected| C
    G["⚠️ No auth layer<br/>→ deploy inside VPC / intranet"] -.-> B
```

---

## 24. ⚠️ Limitations

Stated plainly, because a governance tool that oversells itself is worse than no tool.

| Limitation | Detail |
|---|---|
| **Physical Progress Sparsity** | Physical progress tracking is sparse — available in **< 5%** of historical data. Physical-trajectory features are therefore frequently missing. |
| **Non-Causal Predictions** | Features such as past cost revisions are **predictive** of future revisions, but do **not imply causality**. SANKET forecasts; it does not explain root cause. |
| **No Automatic Retraining** | The ML model is **frozen**. Any concept drift in macroeconomic conditions requires a **manual retraining cycle**. |
| **Resource Constraints** | No standalone authorization layer; assumes internal deployment. |
| **Historical metrics only** | Validation metrics represent historical evaluation and are not guarantees of future performance. |
| **Advisory, not statutory** | The model prioritizes audits. It does not issue penalties or determine contractor liability. |

---

## 25. 🛣️ Future Work

- 🛰️ **Satellite & geospatial integration** — expanding data integrations to include satellite imagery and geospatial analysis for ground-truth physical progress validation. This directly attacks the physical-progress sparsity limitation above.
- 📉 **Automated ML monitoring** — implementing drift detection to trigger model retraining, replacing the current manual cycle.
- ⚖️ **Deeper governance modelling** — extending statutory transitions and SLA countdowns in the governance state machine.

```mermaid
flowchart LR
    L1["< 5% physical<br/>progress coverage"] -->|satellite + geospatial| F1["Ground-truth<br/>physical validation"]
    L2["Frozen model,<br/>manual retrain"] -->|drift detection| F2["Automated<br/>retraining triggers"]
    L3["Basic state machine"] -->|statutory logic| F3["SLA countdowns +<br/>statutory transitions"]
```

---

## 26. ❓ FAQ

<details>
<summary><b>Why not just flag any project whose cost was revised?</b></summary>

Because that is the current-state approach, and it is *definitionally* late — a revision is the administrative record of a failure that already happened. At matched alert burden, that approach yields a median of 2.0 months of warning against SANKET's 4.0 months.
</details>

<details>
<summary><b>Why a 12-month forward horizon?</b></summary>

It is long enough for remediation to be meaningful and short enough to be labellable across a 2001–2026 dataset without discarding excessive recent history to censoring.
</details>

<details>
<summary><b>Why is PR-AUC reported ahead of ROC-AUC?</b></summary>

Distress events are the minority class. ROC-AUC can look comfortable on imbalanced data; PR-AUC is the stricter, more honest reflection of performance when positives are rare.
</details>

<details>
<summary><b>Why is the model frozen instead of retraining monthly?</b></summary>

Auditability. An alert raised six months ago must be reproducible today, feature-for-feature. Automatic retraining would make every past alert unreproducible. Drift is handled by an explicit, deliberate manual retraining cycle — see the roadmap.
</details>

<details>
<summary><b>Does the AI layer influence the risk score?</b></summary>

No. Gemini is strictly read-only. It reads predictions, trajectories, and TreeSHAP attributions, and returns language. It has no write path to probabilities, tiers, or governance states.
</details>

<details>
<summary><b>Why are the alert thresholds so close together (0.40 / 0.45 / 0.50)?</b></summary>

They encode escalating *institutional cost*, not escalating certainty. Broad surveillance is cheap; ministerial escalation is expensive. The spacing is an operational-burden decision made on a calibrated probability scale.
</details>

<details>
<summary><b>Can this run on a small server?</b></summary>

Yes. Chunked, partition-based incremental processing keeps peak memory strictly under 512MB, which is the design target for micro-instances.
</details>

<details>
<summary><b>What happens if a PDF is re-issued or corrected?</b></summary>

The content hash changes, the affected `(project, month)` pairs are isolated, and the minimal set of downstream artifacts is rebuilt — including peer-cohort backfills for every project whose normalization denominators shifted.
</details>

---

## 27. 📖 Glossary

| Term | Meaning |
|---|---|
| **Trajectory monitoring** | Modelling the *direction and momentum* of a project over time, rather than its snapshot state |
| **Velocity ($V$)** | First derivative — month-over-month rate of change of a metric |
| **Acceleration ($A$)** | Second derivative — whether velocity is itself increasing or decaying |
| **EWMA** | Exponentially weighted moving average — a recency-weighted trend estimate |
| **Right censoring** | An observation whose forward window is not fully observable; excluded, never imputed |
| **Point-in-time (PIT)** | Using only information that existed at or before month $t$ |
| **Walk-forward validation** | Training on the past and testing strictly on the future, fold after fold |
| **Horizon buffer** | A 12-month gap between train and test to prevent label-window bleed |
| **Peer cohort** | Projects sharing `(reporting_month, sector_clean, scale_bucket)` |
| **Isotonic calibration** | A monotonic transform mapping model scores to trustworthy probabilities |
| **Brier score** | Mean squared error of predicted probabilities — lower is better |
| **PR-AUC** | Area under the precision–recall curve; the preferred metric under class imbalance |
| **TreeSHAP** | Exact SHAP attributions for tree models — per-feature contributions to a single prediction |
| **Content-addressed manifest** | Tracking inputs by content hash, enabling true idempotency |
| **Incremental parity** | The guarantee that an incremental run equals a full rebuild |
| **PAIMANA** | The official identifier source used for project identity canonicalization |
| **PMU** | Project Management Unit — the oversight body acting on REVIEW-tier alerts |
| **Alert burden** | The share of the portfolio flagged for audit at a given threshold (~8% here) |

---

## 28. 📁 Repository Structure

```text
.
├── DATA/                   # Local databases and dataset files
├── DATA(RAW)/              # Raw input PDFs
├── configs/                # Configuration files (model.yaml)
├── docs/                   # Documentation and audit logs
├── frontend/               # Vanilla JS dashboard
├── sanket/                 # Core Python package
│   ├── api.py              # FastAPI application
│   ├── db.py               # SQLite/PostgreSQL connection pool
│   ├── model.py            # Frozen LightGBM wrapper
│   └── *_incremental.py    # Chunked, partition-based pipeline
├── scripts/                # Utility and extraction scripts
├── tests/                  # Pytest suite
├── run_incremental_pipeline.py
├── render.yaml             # Render deployment config
└── requirements.txt
```

### Where to start reading the code

```mermaid
flowchart TD
    A["run_incremental_pipeline.py<br/>👈 start here"] --> B["sanket/*_incremental.py<br/>chunked pipeline stages"]
    B --> C["sanket/model.py<br/>frozen LightGBM wrapper"]
    C --> D["sanket/api.py<br/>FastAPI routes"]
    D --> E["sanket/db.py<br/>storage abstraction"]
    D --> F["frontend/<br/>dashboard"]
    G["tests/<br/>read these to learn the invariants"] -.-> B
```

---

## 🧭 Research / Engineering Position

SANKET demonstrates that shifting from **static current-state monitoring** to **longitudinal trajectory-aware modelling** significantly increases the early-warning lead time for infrastructure distress.

By successfully implementing a strictly **point-in-time**, **chunked incremental** pipeline, SANKET provides an **operationally viable predictive governance tool** capable of running on minimal hardware resources.

The contribution is threefold:

1. **Conceptual** — reframing infrastructure oversight from state to derivative, doubling median lead time at matched alert burden (4.0 vs 2.0 months).
2. **Methodological** — a leakage-hardened, censoring-honest, peer-normalized, point-in-time labelling and validation regime, verified by a replay engine rather than asserted.
3. **Engineering** — a fully incremental pipeline with correct cross-entity dependency propagation, running under 512MB, with 106 tests enforcing parity against a full rebuild.

---

<div align="center">

**SANKET** — *System for Analytics and Knowledge on Engineering Trajectories*

Monitor the direction, not just the state.

</div>