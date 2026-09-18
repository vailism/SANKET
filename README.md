# SANKET

SANKET (System for Analytics and Knowledge on Engineering Trajectories) is an AI-powered early-warning system for large public infrastructure projects. It continuously ingests monthly administrative reports and uses machine learning to predict upcoming cost and schedule overruns, moving oversight from reactive state-monitoring to predictive trajectory-monitoring.

## The Problem

Traditionally, infrastructure governance relies on monitoring the *current state* of a project. However, by the time a project officially reports a "cost overrun" or a major "schedule delay," the technical or financial failure has already occurred on the ground months prior. Reporting is fundamentally lagged by administrative approvals. Monitoring current state alone provides reporting, not early warning.

## The Core Idea

"Monitor the direction, not just the state."

SANKET tracks the longitudinal trajectory of projects over time. By calculating the first and second derivatives (velocity and acceleration) of financial expenditure, physical progress, and schedule drift, SANKET detects deteriorating project momentum and predicts distress 3 to 11 months before it is officially recorded as an overrun.

## How SANKET Works

SANKET processes data through a strict chronological pipeline:

`Project Data` → `Canonicalization` → `Timeline Construction` → `Trajectory Features` → `Risk Prediction` → `Risk Tier` → `Governance/Recovery` → `Authority Escalation`

*Note: SANKET provides early-warning predictive alerts to optimize audit and review prioritization. The ML model does not automatically issue legal/regulatory penalties or determine contractor liability.*

## System Architecture

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

## Data Pipeline

The data pipeline strictly separates extraction from downstream temporal engineering:

1. **NEW PDF**: Raw project monitoring reports.
2. **MANIFEST**: Content-addressed idempotent tracking of parsed files.
3. **EXTRACTION**: Optical extraction of tables to raw observations.
4. **CANONICAL**: Deduplication and rule-based cleaning.
5. **TIMELINE**: Assembling longitudinal monthly timeseries per project.
6. **TRAJECTORY**: Computing rolling velocities and accelerations.
7. **TARGET**: Point-in-time calculation of forward-looking distress.
8. **FEATURES**: Constructing the final ML inference matrix.
9. **PORTFOLIO**: Batch updating the current active risk predictions.

### Incremental Storage/I/O
The pipeline is **fully incremental** in both mathematical compute and I/O. Using `ingestion_manifest.json`, SANKET detects exactly which PDFs changed, isolates the affected `(project, month)` pairs, and propagates the minimal required changes through the pipeline. Large datasets (e.g., `project_monthly.csv` and timeline partitions) are updated chunk-by-chunk and partition-by-partition, keeping peak memory strictly under 512MB for horizontal scalability on micro-instances.

## Dataset

*(Verified current baseline)*

- **354** tracked PDF reports
- **1,118,502** raw extraction records
- **478,356** canonical project-month records
- **125,124** archive entities
- **Date Range**: 2001-10 → 2026-07

*Note: Archive entities include historical variations and minor name changes. The active modeling dataset comprises 9,907 eligible genuine unique projects.*

## Project Identity / Data Quality

Raw records undergo extensive sanitation:
- Project identities are canonicalized based on similarity heuristics and PAIMANA official identifiers where available.
- Conflicting duplicate observations for the same `(project_id, reporting_month)` are reconciled via max-conservative merging.
- Synthetic/front-matter artifacts (e.g., table of contents misidentified as projects) are filtered.
- Right-censored observations (where the future is unknown) are strictly marked as `NaN` and dropped from training, never assumed to be zero.

## Machine Learning

The production model is a **LightGBM Classifier** with **Isotonic Calibration**.
It operates as a **frozen production artifact** (`vigil_production_model.joblib`) and is not automatically retrained during standard monthly incremental ingestion. 

## Production Features

Features are engineered strictly from data available at or before the prediction month $t$.

### Financial trajectory
- `V_fin_1m`, `V_fin_3m`, `A_fin`, `EWMA_V_fin`

### Expenditure trajectory
- `V_exp_1m`, `V_exp_3m`, `A_exp`

### Cost/schedule
- `cost_revision_ratio`, `expenditure_to_baseline`, `schedule_deviation_months`, `schedule_deviation_change`, `completion_date_drift`

### Peer/context
- `Z_peer_V_fin`, `sector_clean`, `scale_bucket`

### Trajectory & Physical
- `trajectory_risk_score`, `V_phys_1m`, `V_phys_3m`, `A_phys`, `financial_physical_gap`

### Temporal/history
- `project_age_months`, `observation_number`, `months_since_previous_observation`, `reporting_gap_flag`

### Baseline
- `C_base`

## Target Definition

SANKET predicts a 12-month forward horizon.

**Primary target:** `overrun_composite_12m`
This is a logical `OR` between:
1. `cost_overrun_12m`: A >=5% increase in the revised cost baseline within 12 months.
2. `schedule_overrun_12m`: A >=6.0 month forward drift in the anticipated completion date or official schedule deviation within 12 months.

Incomplete future windows (right censoring) are excluded, not imputed as negative.

## Leakage Prevention

SANKET strictly adheres to point-in-time constraints:
- Evaluated via strict chronological walk-forward validation with a 12-month forward horizon safety buffer (max(train) < min(test)).
- Replay engines simulate historical environments without future knowledge.
- Peer statistics (`Z_peer_V_fin`) are computed purely on trailing cohorts.

## Model Validation

*Verified Out-of-Fold (OOF) Metrics (N = 56,514 test observations across 9,907 projects):*

- **Global OOF PR-AUC:** 0.6467
- **Global OOF ROC-AUC:** 0.7639
- **Global OOF Brier Score:** 0.1926 (Isotonic Calibrated: 0.1824)

*Note: Validation metrics represent historical evaluation and are not guarantees of future performance.*

## Alert Thresholds

The calibrated model probabilities map to specific operational governance tiers:

- **NORMAL:** < 0.40
- **WATCH:** >= 0.40 (Broad Surveillance)
- **REVIEW:** >= 0.45 (Prioritized PMU Scrutiny)
- **ESCALATE:** >= 0.50 (High-confidence Minister/Authority Review)

*These are risk identification tiers. Business logic—not the ML model—governs statutory transitions or official project recovery tracking.*

## Trajectory vs Current-State Monitoring

At a matched operational alert burden (identifying ~8% of the portfolio for audit), the trajectory features provide a median of **4.0 months of early warning** compared to **2.0 months** for current-state static heuristics, while maintaining a false-alert rate of 2.38% (at threshold=0.50).

## Replay Engine

SANKET includes a Point-in-Time replay engine that allows auditors to "time travel" to any historical month, feed the exact information available at that time into the model, and simulate the generated risk alerts alongside the actual real-world outcome, providing transparent validation of the model's predictive lead time.

## Data Dependency Propagation

Because some features (e.g. `Z_peer_V_fin`) are normalized against peer cohorts sharing the same `(reporting_month, sector_clean, scale_bucket)`, SANKET's incremental pipeline correctly identifies when an edit to a single project cascades to alter the normalization denominators of its peers, gracefully backfilling affected peer trajectories.

## Operational Governance

Projects flagged by the SANKET engine enter an operational state machine tracked in the database:
`NORMAL` → `WATCH` → `CONTRACTOR_WARNING` → `RESPONSE_SUBMITTED` → `UNDER_RECOVERY` → `RECOVERED`

Or, upon persistent deterioration:
`UNDER_RECOVERY` → `PERSISTENT_DETERIORATION` → `AUTHORITY_ESCALATION`

## AI Explanation Layer

SANKET integrates the **Gemini 1.5 Flash** API (`@google/genai` SDK) to translate complex TreeSHAP feature importances and raw trajectory data into natural language project briefs and conversational Q&A. The AI serves strictly as an explanatory assistant and is **read-only**—it does not alter the risk probability, issue alerts, or modify project states.

## API

The backend is built on **FastAPI** (`uvicorn`). Key endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service status |
| GET | `/api/projects` | List all tracked projects |
| GET | `/api/projects/{id}` | Fetch project details and latest predictions |
| GET | `/api/projects/{id}/timeline` | Fetch full longitudinal history |
| GET | `/api/projects/{id}/replay` | Simulate historical point-in-time predictions |
| GET | `/api/dashboard/summary` | Aggregate portfolio risk stats |
| POST| `/api/monitor/projects` | Register a project for active governance |
| POST| `/api/ai/project-brief` | Generate a Gemini-powered summary report |
| POST| `/api/assistant` | Conversational query over project state |

## Database

SANKET supports dual database modes via connection pooling:
- **SQLite (WAL mode):** Default zero-config storage for local development (`DATA/monitoring.db`).
- **PostgreSQL:** Production deployment using `psycopg2` when `DATABASE_URL` is provided.

## Frontend

The frontend is a lightweight **Vanilla JS** application (`HTML`, `CSS`, and `JS`) utilizing Tailwind-style utilities. It requires no Node.js build step for core execution. It includes interactive charts, a replay UI, governance intervention tracking, and AI explanation panels.

## Deployment

SANKET is fully configured for deployment on **Render** (via `render.yaml`).
- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn sanket.api:app --host 0.0.0.0 --port $PORT`
- **Port:** Managed via `$PORT` environment variable.

## Environment Variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://user:pass@host/dbname  # Optional: defaults to local SQLite if omitted
SANKET_STORAGE_MODE=local
```

## Local Development

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

## Testing

Run the test suite (106 tests covering model leakage, idempotency, incremental parity, API, and target definitions):

```bash
python3 -m pytest tests/
```

## Security

- CORS is strictly configured in FastAPI.
- Secret keys (e.g. `GEMINI_API_KEY`) are required via environment variables.
- SQL operations utilize parameterized queries (`psycopg2` placeholders and SQLite `?` bindings) to prevent SQL injection.
- (Limitation) SANKET currently does not implement user authentication/authorization; it is designed to run in a protected VPC/intranet environment.

## Limitations

- **Physical Progress Sparsity:** Physical progress tracking is sparse (available in <5% of historical data). 
- **Non-Causal Predictions:** Features like past cost revisions are predictive of future revisions, but do not imply causality.
- **No Automatic Retraining:** The ML model is frozen. Any concept drift in macroeconomic conditions requires a manual retraining cycle.
- **Resource Constraints:** No standalone authorization layer; assumes internal deployment.

## Future Work

- Expanding data integrations to include satellite imagery and geospatial analysis for ground-truth physical progress validation.
- Implementing automated ML monitoring (drift detection) to trigger model retraining.
- Extending statutory transitions and SLA countdowns in the governance state machine.

## Repository Structure

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

## Research / Engineering Position

SANKET demonstrates that shifting from static current-state monitoring to longitudinal trajectory-aware modeling significantly increases the early-warning lead time for infrastructure distress. By successfully implementing a strictly point-in-time, chunked incremental pipeline, SANKET provides an operationally viable predictive governance tool capable of running on minimal hardware resources.
