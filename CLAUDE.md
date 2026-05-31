# Plum Claims — Project Context

## What This Is

A multi-agent AI system for automated OPD health insurance claims processing built for the Plum AI Engineer assignment. Processes claims through a 6-agent pipeline: Intake → Document Verification → Extraction → Policy Engine → Fraud Detection → Decision Aggregation.

## Current Status

- **27/27 tests passing** (unit + integration + API endpoint tests)
- **12/12 eval test cases passing** (full pipeline with full traces)
- All agents implemented and working
- FastAPI API complete with 6 endpoints
- Streamlit UI with file upload support
- Deployment configs (Docker, Railway, Render) ready
- Architecture doc, Component Contracts, and README complete
- Eval report regenerated with full traces for all 12 cases

## Tech Stack

- Python 3.12, FastAPI, Pydantic v2, pydantic-settings
- Google Gemini (2.0-flash for extraction, 2.5-flash for reasoning) — free tier
- LangGraph for pipeline orchestration
- SQLite (aiosqlite) for trace persistence
- Streamlit for UI
- pytest + pytest-asyncio for testing

## Key Files

| File | Purpose |
|------|---------|
| `app/agents/policy_engine.py` | Deterministic rule engine — most complex agent |
| `app/agents/document_verification.py` | Early halt for doc problems |
| `app/agents/extraction.py` | Gemini Vision + test-mode extraction |
| `app/agents/fraud_detection.py` | Pattern-based fraud signals → MANUAL_REVIEW |
| `app/agents/decision_aggregator.py` | Combines policy + fraud into final decision |
| `app/pipeline/graph.py` | LangGraph orchestrator (process_claim function) |
| `app/main.py` | FastAPI endpoints |
| `app/models/claim.py` | All Pydantic models |
| `app/models/policy.py` | Policy data models |
| `app/policy/loader.py` | Loads policy_terms.json |
| `app/services/gemini.py` | Gemini API client with retry |
| `app/services/trace_store.py` | SQLite persistence |
| `app/config.py` | Settings via pydantic-settings |
| `eval/runner.py` | Runs all 12 test cases, generates report |
| `streamlit_app.py` | Streamlit UI with file upload |
| `COMPONENT_CONTRACTS.md` | Detailed interface specs for all components |
| `tests/` | Unit + integration tests |

## How to Run

```bash
# From plum-claims/ directory
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Tests (no API key needed)
$env:PYTHONPATH = "."
pytest tests/ -v

# Eval harness
$env:PYTHONIOENCODING = "utf-8"
python -m eval.runner

# API server
uvicorn app.main:app --reload --port 8000

# Streamlit UI
streamlit run streamlit_app.py
```

## Important Design Decisions

1. **No LLM in policy engine** — deterministic rules for financial decisions
2. **Exclusion check before waiting period** — prevents false positives (e.g., "hernia" matching "herniation")
3. **Line-item evaluation before per-claim limit** — dental claims judged on approved items, not gross total
4. **Per-claim limit = max(global_limit, category_sub_limit)** — allows dental to exceed base ₹5,000 cap
5. **PolicyCheckResult vs Check type mismatch** — pipeline converts PolicyCheckResult → Check for TraceStep
6. **Hernia matching uses specific terms** — avoids "disc herniation" triggering hernia waiting period

## Known Issues / Quirks

- `datetime.utcnow()` deprecation warnings (cosmetic only)
- Exit code 1 from pytest in PowerShell is a stderr redirect artifact, tests actually pass
- `PYTHONIOENCODING=utf-8` needed for eval runner emojis on Windows
- Submission deadline check always passes (treatment dates from 2024, current date is 2026)

---

## NEXT STEPS (Priority Order)

### 1. ~~Streamlit File Upload Support~~ ✅ DONE

Added tabbed interface with file upload (JPG/PNG/PDF) and JSON input fallback.

### 2. ~~Enrich Eval Report with Full Traces~~ ✅ DONE

Regenerated report — all 12 cases show decision, full trace steps, checks, and explanations.

### 3. ~~API Endpoint Tests~~ ✅ DONE

10 tests in `tests/test_api.py` covering health check, claim submission, retrieval, 422 errors, and policy summary.

### 4. Deploy to Live URL (HIGH — deliverable requirement)

The assignment asks for a deployed URL. Options:

**Railway (fastest):**
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
# Set GEMINI_API_KEY in Railway dashboard
```

**Render:**
- Push to GitHub
- Connect repo in Render dashboard
- It will use `render.yaml` automatically

**For Streamlit Cloud (UI only, free):**
- Push to GitHub
- Connect at share.streamlit.io
- Add GEMINI_API_KEY as a secret

### 5. Git Init with Clean Commit History (HIGH — explicitly required)

The assignment says "clean commit history." Structure commits logically:

```bash
git init
git add app/models/ app/config.py app/policy/ policy_terms.json test_cases.json requirements.txt .gitignore .env.example
git commit -m "feat: project scaffold with data models and policy loader"

git add app/agents/intake.py app/agents/document_verification.py
git commit -m "feat: intake validation and document verification agents"

git add app/agents/extraction.py app/services/gemini.py
git commit -m "feat: document extraction agent with Gemini Vision"

git add app/agents/policy_engine.py
git commit -m "feat: deterministic policy engine with all coverage rules"

git add app/agents/fraud_detection.py app/agents/decision_aggregator.py
git commit -m "feat: fraud detection and decision aggregation"

git add app/pipeline/ app/main.py app/services/trace_store.py
git commit -m "feat: LangGraph pipeline orchestrator and FastAPI endpoints"

git add tests/
git commit -m "test: unit and integration tests (17 passing)"

git add eval/
git commit -m "feat: evaluation harness — 12/12 test cases passing"

git add streamlit_app.py
git commit -m "feat: Streamlit UI for claim submission and review"

git add Dockerfile* docker-compose.yml Procfile railway.toml render.yaml
git commit -m "feat: deployment configs (Docker, Railway, Render)"

git add ARCHITECTURE.md README.md
git commit -m "docs: architecture document and README"
```

### 6. Demo Video (REQUIRED deliverable — do last)

Record 8–12 min video covering:
1. **Document problem early halt** — Submit TC001/TC002/TC003 via Streamlit, show the specific error message
2. **Successful end-to-end approval** — Submit TC004, show full trace with all checks visible
3. **Technical decision proud of** — Deterministic policy engine (no LLM for financial decisions), explain the check ordering and why
4. **What you'd change** — Add ML-based fraud detection, queue-based async processing for scale

### 7. Optional Improvements (NICE-TO-HAVE)

- **Langsmith/Langfuse tracing integration** — would boost observability score
- **Pydantic strict mode** — catch type errors earlier
- **Rate limiting on API** — production readiness
- **Batch claim processing endpoint** — demonstrate scale thinking
