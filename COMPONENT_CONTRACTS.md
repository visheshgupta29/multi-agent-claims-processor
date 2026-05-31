# Component Contracts

> For every significant component in your system, define its interface: what it accepts as input, what it produces as output, and what errors it can raise.

---

## 1. Intake Validation Agent

**Module:** `app/agents/intake.py`

### Interface

```python
def validate_intake(request: ClaimRequest, policy: PolicyTerms) -> IntakeResult
```

### Input

| Field | Type | Description |
|-------|------|-------------|
| `request` | `ClaimRequest` | Full claim submission with member_id, category, amount, documents |
| `policy` | `PolicyTerms` | Loaded policy configuration |

### Output: `IntakeResult`

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | Whether all intake checks passed |
| `error_message` | `str \| None` | Human-readable error if failed |
| `checks` | `list[Check]` | All checks performed with PASS/FAIL results |
| `member_name` | `str` | Resolved member name (empty if not found) |

### Errors

- Does not raise exceptions. All failures are captured in `IntakeResult.passed = False`.
- Invalid policy_id → immediate FAIL with specific message
- Member not found → immediate FAIL naming the missing member_id
- No documents → immediate FAIL
- Amount ≤ 0 → immediate FAIL

---

## 2. Document Verification Agent (GATE)

**Module:** `app/agents/document_verification.py`

### Interface

```python
def verify_documents(request: ClaimRequest, policy: PolicyTerms) -> DocumentVerificationResult
```

### Input

| Field | Type | Description |
|-------|------|-------------|
| `request` | `ClaimRequest` | Claim with documents array |
| `policy` | `PolicyTerms` | Policy with document_requirements per category |

### Output: `DocumentVerificationResult`

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | Whether documents are acceptable |
| `halt` | `bool` | If true, pipeline stops immediately (no further processing) |
| `error_message` | `str \| None` | **Specific, actionable** message for the member |
| `checks` | `list[Check]` | All verification checks performed |

### Error Messages (guaranteed format)

- **Missing document:** "Your {category} claim is missing required documents. You uploaded: {types}. Missing: {types}. Please upload the following document(s) to proceed: {types}."
- **Unreadable document:** "The following document(s) cannot be read: {doc_type} ({file_name}). The image appears to be blurry or unreadable. Please re-upload a clear photo or scan of the document(s)."
- **Name mismatch:** "The uploaded documents appear to belong to different patients. Names found — {type}: '{name}'; {type}: '{name}'. All documents for a claim must belong to the same patient."

### Errors

- Does not raise exceptions. All failures are captured in the result object.
- This is the **GATE** node — if `halt=True`, no further pipeline processing occurs.

---

## 3. Data Extraction Agent

**Module:** `app/agents/extraction.py`

### Interface

```python
async def extract_from_documents(
    request: ClaimRequest,
    simulate_failure: bool = False,
) -> ExtractedClaimData
```

### Input

| Field | Type | Description |
|-------|------|-------------|
| `request` | `ClaimRequest` | Claim with documents (may have `content` dict or `file_data` bytes) |
| `simulate_failure` | `bool` | If true, raises ExtractionComponentError on last document |

### Output: `ExtractedClaimData`

| Field | Type | Description |
|-------|------|-------------|
| `documents` | `list[ExtractedDocumentData]` | Per-document extraction results |
| `primary_diagnosis` | `str \| None` | First diagnosis found across documents |
| `primary_patient_name` | `str \| None` | Patient name from documents |
| `primary_doctor_name` | `str \| None` | Doctor name from documents |
| `hospital_name` | `str \| None` | Hospital/clinic name |
| `total_billed_amount` | `float \| None` | Total from bills |
| `overall_confidence` | `float` | Minimum confidence across all documents (0.0–1.0) |

### Extraction Modes

1. **Pre-parsed content** (`doc.content` is set): Extracts from dict directly. Confidence: 0.95.
2. **Gemini Vision** (`doc.file_data` is set): Sends image to Gemini API. Confidence: model-reported.
3. **No data available**: Returns minimal extraction with confidence 0.5.

### Errors

| Error | When | Pipeline Behavior |
|-------|------|-------------------|
| `ExtractionComponentError` | Simulated failure or unrecoverable extraction error | Pipeline catches, uses partial data, reduces confidence |
| `GeminiError` | API timeout/failure after 3 retries | Handled internally, returns low-confidence result |

---

## 4. Policy Engine

**Module:** `app/agents/policy_engine.py`

### Interface

```python
def evaluate_claim(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
) -> PolicyEngineResult
```

### Input

| Field | Type | Description |
|-------|------|-------------|
| `request` | `ClaimRequest` | Original claim request |
| `extracted_data` | `ExtractedClaimData` | Structured data from documents |
| `policy` | `PolicyTerms` | Full policy configuration |

### Output: `PolicyEngineResult`

| Field | Type | Description |
|-------|------|-------------|
| `decision` | `Decision \| None` | APPROVED, PARTIAL, REJECTED, or MANUAL_REVIEW |
| `approved_amount` | `float \| None` | Final amount after all deductions |
| `rejection_reasons` | `list[str]` | Coded reasons (e.g., "WAITING_PERIOD", "EXCLUDED_CONDITION") |
| `checks` | `list[PolicyCheckResult]` | Every check with pass/fail, details, and policy rule reference |
| `line_item_decisions` | `list[LineItemDecision]` | Per-item approve/reject for dental/vision |
| `explanation_parts` | `list[str]` | Human-readable explanation components |

### Check Sequence (deterministic order)

1. Category coverage → REJECTED if not covered
2. Submission deadline → REJECTED if late
3. Minimum claim amount → REJECTED if below ₹500
4. Exclusions → REJECTED if diagnosis matches exclusion list
5. Waiting period → REJECTED if within condition-specific or initial waiting period
6. Pre-authorization → REJECTED if required but missing
7. Line-item evaluation → Filters covered/excluded procedures (dental/vision)
8. Per-claim limit → REJECTED if approvable amount > max(global_limit, category_sub_limit)
9. Amount calculation → Applies network discount then copay
10. Sub-limit check → Informational only
11. Annual OPD limit → Caps approved amount at remaining annual balance

### Invariants

- **Always returns a decision** — never throws for valid input
- **`approved_amount ≤ claimed_amount`** — always
- **Every check is recorded** — both passed and failed
- **No LLM calls** — purely deterministic
- **Amount formula:** `base × (1 - network_discount) × (1 - copay)`

### Errors

- Does not raise exceptions for valid input. All edge cases produce a decision.

---

## 5. Fraud Detection Agent

**Module:** `app/agents/fraud_detection.py`

### Interface

```python
def detect_fraud(request: ClaimRequest, policy: PolicyTerms) -> FraudDetectionResult
```

### Input

| Field | Type | Description |
|-------|------|-------------|
| `request` | `ClaimRequest` | Claim with claims_history for pattern analysis |
| `policy` | `PolicyTerms` | Fraud thresholds configuration |

### Output: `FraudDetectionResult`

| Field | Type | Description |
|-------|------|-------------|
| `requires_manual_review` | `bool` | If true, overrides policy decision to MANUAL_REVIEW |
| `signals` | `list[FraudSignal]` | Detected fraud signals with severity |
| `checks` | `list[Check]` | All fraud checks performed |

### Signals Detected

| Signal | Severity | Trigger |
|--------|----------|---------|
| `SAME_DAY_CLAIMS_EXCEEDED` | HIGH | ≥ `same_day_claims_limit` claims on treatment date |
| `HIGH_VALUE_CLAIM` | MEDIUM | Amount > `auto_manual_review_above` threshold |
| `MONTHLY_CLAIMS_EXCEEDED` | MEDIUM | > `monthly_claims_limit` claims in same month |

### Guarantee

**Never rejects a claim.** Only routes to manual review. The decision aggregator applies this override.

### Errors

- Does not raise exceptions. Missing claims_history is handled gracefully (all checks pass).

---

## 6. Decision Aggregator

**Module:** `app/agents/decision_aggregator.py`

### Interface

```python
def aggregate_decision(
    claim_id: str,
    request: ClaimRequest,
    policy_result: PolicyEngineResult,
    fraud_result: FraudDetectionResult,
    extracted_data: ExtractedClaimData,
    trace_steps: list[TraceStep],
    component_failures: list[str],
) -> ClaimDecision
```

### Input

All upstream results plus the accumulated trace.

### Output: `ClaimDecision`

| Field | Type | Description |
|-------|------|-------------|
| `claim_id` | `str` | Generated claim identifier (CLM_XXXXXXXX) |
| `decision` | `Decision \| None` | Final decision (None = halted before decision) |
| `approved_amount` | `float \| None` | Amount approved (if any) |
| `rejection_reasons` | `list[str]` | Coded rejection reasons |
| `confidence_score` | `float` | 0.0–1.0, reduced by failures and low extraction confidence |
| `explanation` | `str` | Human-readable explanation of the decision |
| `line_item_decisions` | `list[LineItemDecision]` | Per-item decisions (dental/vision) |
| `policy_checks` | `list[PolicyCheckResult]` | All policy checks with results |
| `fraud_signals` | `list[FraudSignal]` | Detected fraud patterns |
| `manual_review_recommended` | `bool` | True if fraud signals or component failures |
| `error_message` | `str \| None` | Set for halted claims (document issues) |
| `trace` | `ClaimTrace` | Full processing trace with all steps |

### Decision Priority

1. Fraud signals present → `MANUAL_REVIEW`
2. Policy says REJECTED → `REJECTED`
3. Policy says PARTIAL → `PARTIAL`
4. Policy says APPROVED → `APPROVED`

### Confidence Adjustments

- Each component failure: -0.2 (minimum 0.3)
- Fraud signals: capped at 0.6
- Low extraction confidence: flows through from extraction

---

## 7. Pipeline Orchestrator

**Module:** `app/pipeline/graph.py`

### Interface

```python
async def process_claim(request: ClaimRequest) -> ClaimDecision
```

### Input

| Field | Type | Description |
|-------|------|-------------|
| `request` | `ClaimRequest` | Complete claim submission |

### Output

Always returns a `ClaimDecision`. Never throws to the caller.

### Flow Control

```
Intake → [passes?] → Document Verification → [halt?] → Extraction → Policy → Fraud → Aggregation
         ↓ fails                              ↓ halt
    HALT decision                       HALT decision (specific error message)
```

### Error Handling at Each Step

| Step | On Exception | Behavior |
|------|-------------|----------|
| Intake | Caught | Added to component_failures, continues |
| Document Verification | Caught | Added to component_failures, continues |
| Extraction | ExtractionComponentError | Uses partial data, reduces confidence |
| Policy Engine | Caught | Sets decision to MANUAL_REVIEW |
| Fraud Detection | Caught | Added to component_failures, continues |

---

## 8. Trace Store

**Module:** `app/services/trace_store.py`

### Interface

```python
class TraceStore:
    def save_decision(self, decision: ClaimDecision, request_data: dict = None) -> None
    def get_decision(self, claim_id: str) -> dict | None
    def get_trace(self, claim_id: str) -> dict | None
    def list_claims(self, member_id: str = None, limit: int = 50) -> list[dict]
```

### Storage

- SQLite database at `DATABASE_PATH` (default: `./data/traces.db`)
- Stores full decision JSON and trace JSON
- Indexed by claim_id and member_id
- Created automatically on first use

### Errors

- `save_decision`: Uses INSERT OR REPLACE (idempotent)
- `get_decision`/`get_trace`: Returns None if not found (caller handles 404)

---

## 9. FastAPI Application

**Module:** `app/main.py`

### Endpoints

| Route | Method | Input | Output | Errors |
|-------|--------|-------|--------|--------|
| `/health` | GET | — | `{"status": "healthy"}` | — |
| `/api/claims/submit` | POST | `ClaimRequest` (JSON body) | `ClaimDecision` | 422 (validation), 500 (internal) |
| `/api/claims/{claim_id}` | GET | Path param | Stored decision | 404 (not found) |
| `/api/traces/{claim_id}` | GET | Path param | Trace JSON | 404 (not found) |
| `/api/claims` | GET | Query: `member_id`, `limit` | `{"claims": [...], "count": N}` | — |
| `/api/policy/summary` | GET | — | Policy summary object | — |

### Error Responses

- **422 Unprocessable Entity**: Pydantic validation failure. Returns field-level errors.
- **404 Not Found**: Claim or trace not found by ID.
- **500 Internal Server Error**: Unhandled exception during processing. Returns error detail string.

---

## Data Models Summary

### ClaimRequest (Input)

```python
{
    "member_id": str,                    # Required: e.g. "EMP001"
    "policy_id": str,                    # Default: "PLUM_GHI_2024"
    "claim_category": ClaimCategory,     # Required: enum value
    "treatment_date": str,               # Required: "YYYY-MM-DD"
    "claimed_amount": float,             # Required: > 0
    "hospital_name": str | None,         # Optional
    "ytd_claims_amount": float,          # Default: 0
    "documents": list[DocumentInput],    # Required: at least 1
    "claims_history": list[ClaimHistoryItem],  # Default: []
    "simulate_component_failure": bool,  # Default: false
}
```

### ClaimDecision (Output)

```python
{
    "claim_id": str,                     # Generated: "CLM_XXXXXXXX"
    "decision": Decision | None,         # APPROVED|PARTIAL|REJECTED|MANUAL_REVIEW|null
    "approved_amount": float | None,     # After all deductions
    "rejection_reasons": list[str],      # Coded reasons
    "confidence_score": float,           # 0.0-1.0
    "explanation": str,                  # Human-readable
    "line_item_decisions": list[...],    # Per-item (dental/vision)
    "policy_checks": list[...],         # All checks with pass/fail
    "fraud_signals": list[...],         # Detected signals
    "manual_review_recommended": bool,   # Fraud or component failure
    "error_message": str | None,         # For halted claims
    "trace": ClaimTrace,                 # Full processing trace
}
```

### ClaimTrace

```python
{
    "claim_id": str,
    "timestamp": datetime,
    "member_id": str,
    "claim_category": str,
    "status": "COMPLETED" | "HALTED_EARLY" | "ERROR",
    "steps": list[TraceStep],            # Every pipeline step
    "final_decision": Decision | None,
    "approved_amount": float | None,
    "confidence_score": float,
    "total_duration_ms": int,
}
```

### TraceStep

```python
{
    "step_name": str,                    # e.g. "policy_evaluation"
    "status": "PASSED" | "FAILED" | "ERROR" | "SKIPPED",
    "started_at": datetime,
    "duration_ms": int,
    "input_summary": dict,               # Key inputs to this step
    "output_summary": dict,              # Key outputs from this step
    "checks_performed": list[Check],     # All checks with results
    "confidence_impact": float,          # How this step affected confidence
}
```
