# Architecture Document

## Health Insurance Claims Processing System

### System Overview

A multi-agent AI system that processes OPD health insurance claims end-to-end: from document verification through policy evaluation to final decision. The system is designed for **explainability**, **graceful degradation**, and **deterministic correctness** where it matters most.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI / Streamlit UI                        │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Pipeline Orchestrator (LangGraph)               │
│                                                                     │
│  ┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌───────┐  │
│  │ Intake │→ │  Doc   │→ │Extraction│→ │Extraction│→ │ Policy │→ │ Fraud │  │
│  │Validate│  │ Verify │  │  (Groq)  │  │Validation│  │ Engine │  │Detect │  │
│  └────────┘  └────────┘  └──────────┘  └──────────┘  └────────┘  └───────┘  │
│                                                              │         │      │
│                                                              ▼         ▼      │
│                                                      ┌──────────────────┐     │
│                                                      │    Aggregator    │     │
│                                                      └──────────────────┘     │
│                                            └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                           ┌──────────────┐
                           │ Trace Store  │
                           │  (SQLite)    │
                           └──────────────┘
```

---

### Design Principles

1. **Determinism over intelligence**: Policy rules are applied deterministically without LLM involvement. The LLM is only used for document extraction where ambiguity is inherent. This means claims get consistent, reproducible decisions.

2. **Fail-open with degraded confidence**: When the extraction component fails, the system doesn't crash — it falls through to policy evaluation with reduced confidence and flags for manual review only if needed.

3. **Early halt for document issues**: Document problems are caught before any expensive processing. The system provides specific, actionable error messages (not generic "upload failed" errors).

4. **Full observability**: Every step produces a trace entry with input/output summaries, checks performed, duration, and confidence impact. A human reviewer can reconstruct the entire decision path.

---

### Components

#### 1. Intake Validation (`app/agents/intake.py`)

**Purpose**: Gate that validates basic eligibility before any document processing.

**Checks**:
- Policy ID validity
- Member exists in roster and is active
- Policy period is current
- Documents are present
- Amount is positive

**Design choice**: This is a fast, synchronous check with no external calls. It prevents wasted compute on clearly invalid requests.

#### 2. Document Verification (`app/agents/document_verification.py`)

**Purpose**: Verify that the right documents were submitted, are readable, and belong to the same patient. This is the **early halt** mechanism.

**Checks**:
- Document completeness (required types present for claim category)
- Document quality (not unreadable/corrupted)
- Patient name consistency across documents

**Key behavior**: On failure, halts the pipeline immediately and returns a specific error message telling the member exactly what's wrong and how to fix it.

#### 3. Data Extraction (`app/agents/extraction.py`)

**Purpose**: Extract structured data from documents. Uses Groq Vision for real documents; uses pre-parsed content in test mode.

**Outputs**: Patient name, diagnosis, treatment, line items, amounts, doctor details, confidence score.

**Failure mode**: Raises `ExtractionComponentError` which the pipeline catches. Processing continues with partial data and reduced confidence.

#### 4. Extraction Validation (`app/agents/extraction_validation.py`)

**Purpose**: Post-extraction coherence layer. Catches cases where individual documents look valid in isolation but the *set* of documents doesn't represent a single, well-formed medical encounter. Runs **after** extraction so it can compare extracted per-document fields, not just user-supplied metadata.

**Checks**:
- `extracted_patient_name_consistency` — patient name extracted from every named document must match.
- `document_date_proximity` — extracted document dates must fall within a 30-day window of each other.
- `category_required_fields` — category-mandatory extracted fields must be present (e.g. CONSULTATION/DENTAL/ALT-MED require `primary_diagnosis`, `primary_patient_name`, `total_billed_amount`).

**Key behavior**: Never halts the pipeline and never auto-rejects. Failures are surfaced as flags. The aggregator escalates an *auto-APPROVE* to `MANUAL_REVIEW` when flags are present and no upstream component has already failed — definitive `REJECTED` / `PARTIAL` outcomes from the policy engine are still trusted, and the graceful-degradation path (component failure) is not double-penalized.

#### 5. Policy Engine (`app/agents/policy_engine.py`)

**Purpose**: Deterministic rule engine. Applies all policy rules from `policy_terms.json` without LLM involvement.

**Check sequence**:
1. Category coverage
2. Submission deadline
3. Minimum claim amount
4. Exclusions
5. Waiting periods
6. Pre-authorization requirements
7. Line-item evaluation (dental/vision procedure filtering)
8. Per-claim limit (against approvable amount)
9. Approved amount calculation (network discount + copay)
10. Sub-limit verification
11. Annual OPD limit

**Key design decisions**:
- Exclusion check runs before waiting period (prevents false positives like "obesity" matching both)
- Line-item evaluation runs before per-claim limit (so dental claims are judged on approved items, not gross total)
- Per-claim limit uses `max(global_limit, category_sub_limit)` as effective cap
- Network discount and copay are applied multiplicatively: `amount × (1 - discount) × (1 - copay)`

#### 6. Fraud Detection (`app/agents/fraud_detection.py`)

**Purpose**: Pattern-based fraud signal detection. Never auto-rejects — only routes to manual review.

**Signals checked**:
- Same-day claims exceeding threshold
- High-value claims above auto-review threshold
- Monthly claims frequency

#### 7. Decision Aggregator (`app/agents/decision_aggregator.py`)

**Purpose**: Combines policy engine, fraud detection, and extraction-validation results into a final decision.

**Priority order**:
1. Fraud signals → MANUAL_REVIEW (overrides policy)
2. Policy REJECTED → REJECTED
3. Policy PARTIAL → PARTIAL
4. Policy APPROVED → APPROVED, **unless** extraction-validation flags are present and no component failure occurred → MANUAL_REVIEW

**Also**: Adjusts confidence for component failures, surfaces extraction-validation flags in the explanation, builds human-readable explanation.

#### 8. Pipeline Orchestrator (`app/pipeline/graph.py`)

**Purpose**: Coordinates the multi-agent flow. Handles errors at each step, builds trace, manages early-halt logic.

**LangGraph integration**: Uses a state graph with conditional edges. Document verification failure halts the graph. Extraction failure triggers graceful degradation.

#### 9. Trace Store (`app/services/trace_store.py`)

**Purpose**: SQLite-backed persistence for claim decisions and traces. Supports querying by claim ID, member ID, status.

---

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/claims/submit` | POST | Submit claim for processing |
| `/api/claims/{claim_id}` | GET | Retrieve decision by claim ID |
| `/api/traces/{claim_id}` | GET | Get full trace for a claim |
| `/api/members/{member_id}/claims` | GET | List all claims for a member |

---

### Trade-offs Made

| Decision | Rationale |
|----------|-----------|
| SQLite over Postgres | Simpler deployment, sufficient for demo. Would swap for production. |
| No LLM in policy engine | Determinism > intelligence for financial decisions. LLMs hallucinate; rules don't. |
| Groq free tier | Cost-effective, sufficient for OCR/extraction. Would use dedicated OCR (Google Document AI) in production. |
| Synchronous pipeline | Simpler debugging and tracing. Would add async queue (Celery/BullMQ) for 10x scale. |
| Pre-parsed content for tests | Avoids external API calls in CI. Real flow uses Vision API. |

---

### Limitations & Scale Considerations

**Current limitations**:
- SQLite doesn't support concurrent writes well
- No retry logic for transient vision API failures beyond basic retries
- Submission deadline check assumes same-day submission (no explicit submission_date field)
- Waiting period keyword matching could miss edge cases

**At 10x scale (750K claims/year)**:
1. **Queue-based processing**: Replace synchronous pipeline with Celery workers + Redis queue
2. **PostgreSQL**: Replace SQLite for ACID compliance and concurrent access
3. **Document preprocessing**: Dedicated Document AI pipeline with CDN-backed document storage
4. **Caching**: Redis cache for policy lookups and member roster (reload on policy changes)
5. **Horizontal scaling**: Stateless workers behind load balancer; each agent could be a separate microservice
6. **ML-based fraud**: Replace rule-based fraud with trained anomaly detection model

---

### Future Improvements

- **Soft LLM coherence layer for `extraction_validation`.** Today the agent applies three deterministic checks (extracted name consistency, date proximity, category-required fields). A natural next step is a fourth, *advisory* check that asks a small model (e.g. `llama-3.1-8b-instant`) "Do these extracted documents describe the same medical encounter?" and returns `{coherent: bool, reason: str}`. The result would not auto-reject \u2014 it would simply add a flag and downgrade confidence, consistent with the current "no LLM in policy" design. Deferred because the deterministic checks already kill the random-document scenario and the LLM call adds latency and a quota dependency to every claim.
- **Cross-document item coherence.** Bill line items should overlap with prescribed medications or ordered tests. Even a simple "\u22651 token overlap" rule would tighten the pharmacy / diagnostic flows.
- **Provider \u2194 prescriber cross-check.** The doctor on the prescription should be plausibly linked to the provider on the bill; mismatch \u2192 fraud signal.
- **Async pipeline** (Celery / BullMQ) and **PostgreSQL trace store** for production scale.

---

### Component Contracts

#### ClaimRequest → Pipeline → ClaimDecision

**Input** (`ClaimRequest`):
```json
{
  "member_id": "string",
  "claim_category": "CONSULTATION|DENTAL|VISION|DIAGNOSTIC|ALTERNATIVE_MEDICINE",
  "treatment_date": "YYYY-MM-DD",
  "claimed_amount": float,
  "hospital_name": "string | null",
  "ytd_claims_amount": float,
  "documents": [DocumentInput],
  "claims_history": [ClaimHistoryItem]
}
```

**Output** (`ClaimDecision`):
```json
{
  "claim_id": "uuid",
  "decision": "APPROVED|PARTIAL|REJECTED|MANUAL_REVIEW|null",
  "approved_amount": float | null,
  "rejection_reasons": ["string"],
  "confidence_score": 0.0-1.0,
  "explanation": "string",
  "line_item_decisions": [LineItemDecision],
  "policy_checks": [PolicyCheckResult],
  "fraud_signals": [FraudSignal],
  "error_message": "string | null",
  "trace": ClaimTrace
}
```

**Errors**:
- Validation errors (422) for malformed requests
- Internal errors (500) are caught and returned as MANUAL_REVIEW with reduced confidence

#### Document Verification Contract

**Input**: `ClaimRequest` with documents
**Output**: `DocumentVerificationResult`
- `passed: bool`
- `halt: bool` — if true, pipeline stops immediately
- `error_message: str | None` — specific, actionable message for the member
- `checks: list[Check]`

**Halt conditions**:
- Required document type missing → "Please upload a [type]. You submitted [what was received]."
- Document unreadable → "Document [file_id] appears to be unreadable. Please upload a clearer image."
- Patient name mismatch → "Documents appear to belong to different patients: [names found]."

#### Policy Engine Contract

**Input**: `ClaimRequest`, `ExtractedClaimData`, `PolicyTerms`
**Output**: `PolicyEngineResult`
- `decision: Decision`
- `approved_amount: float`
- `rejection_reasons: list[str]`
- `checks: list[PolicyCheckResult]`
- `line_item_decisions: list[LineItemDecision]`
- `explanation_parts: list[str]`

**Invariants**:
- Always returns a decision (never throws for valid input)
- `approved_amount` is always ≤ `claimed_amount`
- Every check is recorded whether passed or failed

#### Fraud Detection Contract

**Input**: `ClaimRequest`, `PolicyTerms`
**Output**: `FraudDetectionResult`
- `requires_manual_review: bool`
- `signals: list[FraudSignal]`
- `checks: list[Check]`

**Guarantee**: Never rejects a claim. Only flags for review.

---

### Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| API | FastAPI | Async-native, auto-docs, Pydantic validation |
| UI | Streamlit | Rapid prototyping, built-in state management |
| Orchestration | LangGraph | State graph with conditional edges, built for agent workflows |
| LLM | Groq (Llama 4 Scout + Llama/GPT-OSS text models) | Low-latency, OpenAI-compatible API, strong multimodal support |
| Models | Pydantic v2 | Runtime validation, serialization, IDE support |
| Storage | SQLite + aiosqlite | Zero-config, sufficient for demo |
| Testing | pytest + pytest-asyncio | Async test support, clean fixtures |

---

### Running Locally

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt

# Set API key
echo "GROQ_API_KEY=your-key-here" > .env

# Run API
PYTHONPATH=. uvicorn app.main:app --reload

# Run UI
streamlit run streamlit_app.py

# Run tests
PYTHONPATH=. pytest tests/ -v

# Run eval
PYTHONPATH=. python -m eval.runner
```

### Deployment

The system is deployed as two services:

| Service | Platform | URL |
|---------|----------|-----|
| FastAPI API | Render (free tier) | https://plum-claims-api-ao0h.onrender.com |
| Streamlit UI | Streamlit Cloud (free) | https://multi-agent-claims-process.streamlit.app |

Both auto-deploy on push to `main`.

```bash
# Local Docker
docker-compose up --build
```

---

### Error Handling Philosophy

The system follows a **fail-open with degraded confidence** approach:

| Failure Mode | System Behavior | User Impact |
|---|---|---|
| LLM extraction timeout | Uses partial/fallback data, reduces confidence | Decision still produced, flagged for manual review if confidence < threshold |
| Document unreadable | Halt immediately | Member gets specific re-upload instructions |
| Policy rule ambiguity | Conservative interpretation (deny) | Member can appeal with additional documentation |
| Network/API failure | Retry with exponential backoff (3 attempts) | Slight delay; after retries fail, component marked as failed |
| Invalid input data | 422 with Pydantic validation errors | Clear field-level error messages |

---

### Testing Strategy

| Layer | What's Tested | Test Count |
|-------|--------------|------------|
| Unit — Document Verification | All halt conditions (wrong doc, unreadable, name mismatch) | 4 tests |
| Unit — Policy Engine | All policy rules (TC004–TC012 scenarios) | 9 tests |
| Integration — Full Pipeline | End-to-end through all agents | 4 tests |
| API — Endpoints | HTTP layer, serialization, error codes | 10 tests |
| Eval — Acceptance | All 12 test cases against expected outcomes | 12 cases |

**Total: 27 automated tests + 12 eval cases**

Tests run without API keys (use pre-parsed content). CI-ready.

---

### Considered and Rejected

| Approach | Why Rejected |
|----------|--------------|
| LLM for policy decisions | Non-deterministic; can't guarantee consistent financial outcomes |
| Separate microservices per agent | Over-engineering for current scale; adds deployment complexity |
| PostgreSQL | SQLite sufficient for demo; would switch at production scale |
| LangChain agents with tool-calling | Too much abstraction; simple state graph is more debuggable |
| Celery task queue | Synchronous pipeline is simpler to trace and debug |
| OpenAI GPT-4V over Groq vision stack | Cost barrier for demo; current Groq setup is sufficient |

