# Plum Health Insurance Claims Processing System

## Overview

AI-powered multi-agent system for automated OPD health insurance claims processing. Achieves **12/12 test cases passing** with full observability, graceful degradation, and deterministic policy evaluation.

### Highlights

- **7-agent pipeline**: Intake → Document Verification → Extraction → Extraction Validation → Policy Engine → Fraud Detection → Decision Aggregation
- **27 automated tests** (unit + integration + API endpoint tests)
- **12/12 eval cases** passing with full traces
- **Deterministic policy engine** — no LLM for financial decisions
- **Early halt** with specific, actionable error messages for document issues
- **Graceful degradation** — component failures reduce confidence, don't crash the system
- **Full observability** — every check, step, and confidence impact is recorded in the trace

## Live Demo

| Service | URL |
|---------|-----|
| **Streamlit UI** | https://multi-agent-claims-process.streamlit.app |
| **API** | https://plum-claims-api-ao0h.onrender.com |
| **API Docs** | https://plum-claims-api-ao0h.onrender.com/docs |

## Quick Start (Local)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# Create .env with your Groq API key (only needed for real document uploads)
echo "GROQ_API_KEY=your-key" > .env

# Run tests (no API key needed — 27 tests)
set PYTHONPATH=.
pytest tests/ -v

# Run evaluation harness (no API key needed — 12 test cases)
python -m eval.runner

# Start API server
uvicorn app.main:app --reload --port 8000

# Start Streamlit UI
streamlit run streamlit_app.py
```

## Project Structure

```
├── ARCHITECTURE.md            # System design, contracts, trade-offs
├── Dockerfile                 # API container
├── Dockerfile.streamlit       # UI container
├── docker-compose.yml         # Full stack deployment
├── policy_terms.json          # Policy rules (loaded at runtime)
├── test_cases.json            # 12 test scenarios with expected outcomes
├── app/
│   ├── agents/                # Multi-agent components
│   │   ├── intake.py              # Member eligibility validation
│   │   ├── document_verification.py  # Early halt for doc issues (GATE)
│   │   ├── extraction.py         # Groq Vision data extraction
│   │   ├── extraction_validation.py  # Post-extraction coherence checks (name/date/fields)
│   │   ├── policy_engine.py      # Deterministic rule engine (no LLM)
│   │   ├── fraud_detection.py    # Pattern-based fraud signals
│   │   └── decision_aggregator.py # Final decision builder
│   ├── pipeline/
│   │   └── graph.py              # LangGraph orchestrator
│   ├── models/
│   │   ├── claim.py              # Pydantic models (inputs, outputs, traces)
│   │   └── policy.py             # Policy data models
│   ├── policy/
│   │   └── loader.py             # Policy JSON loader with caching
│   ├── services/
│   │   ├── groq.py               # Groq API client with retry
│   │   └── trace_store.py        # SQLite persistence for traces
│   ├── config.py                 # Settings via pydantic-settings
│   └── main.py                   # FastAPI application (5 endpoints)
├── eval/
│   ├── runner.py                 # Evaluation harness
│   └── eval_report.md            # Generated report (12/12 passing)
├── tests/
│   ├── test_api.py               # API endpoint tests (10 tests)
│   ├── test_policy_engine.py     # Policy rule tests (9 tests)
│   ├── test_document_verification.py  # Doc verification tests (4 tests)
│   └── test_pipeline_integration.py   # Full pipeline tests (4 tests)
├── streamlit_app.py              # Streamlit UI with file upload
└── requirements.txt
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/claims/submit` | POST | Submit claim for processing |
| `/api/claims/{claim_id}` | GET | Retrieve processed decision |
| `/api/traces/{claim_id}` | GET | Get full processing trace |
| `/api/claims` | GET | List recent claims |
| `/api/policy/summary` | GET | Active policy summary |

## Eval Results

```
12/12 test cases passed ✅

TC001: Wrong Document Uploaded                    → HALT     ✅
TC002: Unreadable Document                        → HALT     ✅
TC003: Documents Belong to Different Patients     → HALT     ✅
TC004: Clean Consultation — Full Approval         → APPROVED ✅
TC005: Waiting Period — Diabetes                  → REJECTED ✅
TC006: Dental Partial Approval — Cosmetic Excl.   → PARTIAL  ✅
TC007: MRI Without Pre-Authorization             → REJECTED ✅
TC008: Per-Claim Limit Exceeded                   → REJECTED ✅
TC009: Fraud Signal — Multiple Same-Day Claims    → MANUAL_REVIEW ✅
TC010: Network Hospital — Discount Applied        → APPROVED ✅
TC011: Component Failure — Graceful Degradation   → APPROVED ✅
TC012: Excluded Treatment                         → REJECTED ✅
```

## Key Design Decisions

1. **No LLM in policy engine** — Financial decisions use deterministic rules. LLMs are only used for document extraction where ambiguity is inherent. This ensures consistent, reproducible, auditable decisions.
2. **Early halt for document issues** — Specific, actionable error messages before any expensive processing. Members know exactly what to fix.
3. **Full trace observability** — Every check, every step, every confidence impact is recorded. Operations team can reconstruct any decision.
4. **Graceful degradation** — Component failures reduce confidence but don't crash the system. The system continues with available data.
5. **Exclusion before waiting period** — Prevents false positives (e.g., "disc herniation" shouldn't trigger "hernia" waiting period).

## Deployment

The system is deployed as two services:

- **API (Render)**: Auto-deploys from `render.yaml` on push to `main`. FastAPI with Swagger docs at `/docs`.
- **UI (Streamlit Cloud)**: Connected to GitHub repo, deploys `streamlit_app.py` with full pipeline.

### Local Docker

```bash
# Full stack
docker-compose up --build

# Individual services
docker build -t plum-api -f Dockerfile .
docker build -t plum-ui -f Dockerfile.streamlit .
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Full system design, trade-offs, scale considerations
- **[COMPONENT_CONTRACTS.md](COMPONENT_CONTRACTS.md)** — Interface specifications for every component (inputs, outputs, errors)
- **[eval/eval_report.md](eval/eval_report.md)** — Detailed evaluation results with full traces for all 12 cases
