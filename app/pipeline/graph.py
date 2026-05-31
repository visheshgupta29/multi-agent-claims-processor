"""LangGraph pipeline definition — orchestrates all agents.

Pipeline flow:
  ClaimRequest → Intake → Document Verification (GATE) → Extraction →
  [Policy Engine + Fraud Detection] → Decision Aggregator → ClaimDecision

The Document Verification step is a conditional gate:
- If documents are invalid → HALT (return error immediately)
- If documents are valid → continue to extraction
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import TypedDict, Optional

from app.models.claim import (
    ClaimRequest,
    ClaimDecision,
    ExtractedClaimData,
    TraceStep,
    StepStatus,
    Check,
    Decision,
    TraceStatus,
    ClaimTrace,
)
from app.models.policy import PolicyTerms
from app.policy.loader import load_policy
from app.agents.intake import validate_intake, IntakeResult
from app.agents.document_verification import verify_documents, DocumentVerificationResult
from app.agents.extraction import extract_from_documents, ExtractionComponentError
from app.agents.policy_engine import evaluate_claim, PolicyEngineResult
from app.agents.fraud_detection import detect_fraud, FraudDetectionResult
from app.agents.decision_aggregator import aggregate_decision


class PipelineState(TypedDict):
    """State passed between pipeline nodes."""
    claim_id: str
    request: ClaimRequest
    policy: PolicyTerms
    intake_result: Optional[IntakeResult]
    doc_verification_result: Optional[DocumentVerificationResult]
    extracted_data: Optional[ExtractedClaimData]
    policy_result: Optional[PolicyEngineResult]
    fraud_result: Optional[FraudDetectionResult]
    trace_steps: list[TraceStep]
    component_failures: list[str]
    halted: bool
    final_decision: Optional[ClaimDecision]


async def process_claim(request: ClaimRequest) -> ClaimDecision:
    """Main pipeline entry point — processes a claim through all agents.

    This is the synchronous orchestrator that runs the full pipeline.
    Uses try/except at each step for graceful degradation.
    """
    claim_id = f"CLM_{uuid.uuid4().hex[:8].upper()}"
    policy = load_policy()
    trace_steps: list[TraceStep] = []
    component_failures: list[str] = []

    # --- Step 1: Intake Validation ---
    step_start = time.time()
    try:
        intake_result = validate_intake(request, policy)
        step = TraceStep(
            step_name="intake_validation",
            status=StepStatus.PASSED if intake_result.passed else StepStatus.FAILED,
            started_at=datetime.utcnow(),
            duration_ms=int((time.time() - step_start) * 1000),
            input_summary={"member_id": request.member_id, "claimed_amount": request.claimed_amount},
            output_summary={"passed": intake_result.passed, "member_name": intake_result.member_name},
            checks_performed=intake_result.checks,
        )
        trace_steps.append(step)

        if not intake_result.passed:
            return _build_halt_decision(
                claim_id, request, intake_result.error_message, trace_steps, TraceStatus.HALTED_EARLY
            )
    except Exception as e:
        trace_steps.append(_error_step("intake_validation", str(e), step_start))
        component_failures.append(f"Intake validation failed: {str(e)}")

    # --- Step 2: Document Verification (GATE) ---
    step_start = time.time()
    try:
        doc_result = verify_documents(request, policy)
        step = TraceStep(
            step_name="document_verification",
            status=StepStatus.PASSED if doc_result.passed else StepStatus.FAILED,
            started_at=datetime.utcnow(),
            duration_ms=int((time.time() - step_start) * 1000),
            input_summary={"document_count": len(request.documents),
                          "document_types": [d.actual_type.value if d.actual_type else "UNKNOWN" for d in request.documents]},
            output_summary={"passed": doc_result.passed, "halt": doc_result.halt},
            checks_performed=doc_result.checks,
        )
        trace_steps.append(step)

        # GATE: If documents are invalid, halt immediately
        if doc_result.halt:
            return _build_halt_decision(
                claim_id, request, doc_result.error_message, trace_steps, TraceStatus.HALTED_EARLY
            )
    except Exception as e:
        trace_steps.append(_error_step("document_verification", str(e), step_start))
        component_failures.append(f"Document verification failed: {str(e)}")

    # --- Step 3: Data Extraction ---
    extracted_data = ExtractedClaimData()
    step_start = time.time()
    try:
        extracted_data = await extract_from_documents(
            request,
            simulate_failure=request.simulate_component_failure,
        )
        step = TraceStep(
            step_name="data_extraction",
            status=StepStatus.PASSED,
            started_at=datetime.utcnow(),
            duration_ms=int((time.time() - step_start) * 1000),
            input_summary={"document_count": len(request.documents)},
            output_summary={
                "diagnosis": extracted_data.primary_diagnosis,
                "patient_name": extracted_data.primary_patient_name,
                "confidence": extracted_data.overall_confidence,
            },
            checks_performed=[Check(
                check_name="extraction_confidence",
                result="PASS" if extracted_data.overall_confidence > 0.5 else "FAIL",
                details=f"Overall extraction confidence: {extracted_data.overall_confidence:.2f}",
                relevant_policy_rule="",
            )],
            confidence_impact=-(1.0 - extracted_data.overall_confidence) * 0.1,
        )
        trace_steps.append(step)

    except ExtractionComponentError as e:
        trace_steps.append(_error_step("data_extraction", str(e), step_start))
        component_failures.append(f"Data extraction component failed: {str(e)}")
        # Build partial extracted data from available content
        extracted_data = _build_partial_extraction(request)

    except Exception as e:
        trace_steps.append(_error_step("data_extraction", str(e), step_start))
        component_failures.append(f"Data extraction failed: {str(e)}")
        extracted_data = _build_partial_extraction(request)

    # --- Step 4: Policy Engine ---
    policy_result = PolicyEngineResult()
    step_start = time.time()
    try:
        policy_result = evaluate_claim(request, extracted_data, policy)
        step = TraceStep(
            step_name="policy_evaluation",
            status=StepStatus.PASSED,
            started_at=datetime.utcnow(),
            duration_ms=int((time.time() - step_start) * 1000),
            input_summary={
                "diagnosis": extracted_data.primary_diagnosis,
                "claimed_amount": request.claimed_amount,
                "category": request.claim_category.value,
            },
            output_summary={
                "decision": policy_result.decision.value if policy_result.decision else None,
                "approved_amount": policy_result.approved_amount,
                "rejection_reasons": policy_result.rejection_reasons,
            },
            checks_performed=[
                Check(
                    check_name=c.check_name,
                    result="PASS" if c.passed else "FAIL",
                    details=c.details,
                    relevant_policy_rule=c.policy_rule,
                )
                for c in policy_result.checks
            ],
        )
        trace_steps.append(step)

    except Exception as e:
        trace_steps.append(_error_step("policy_evaluation", str(e), step_start))
        component_failures.append(f"Policy engine failed: {str(e)}")
        policy_result.decision = Decision.MANUAL_REVIEW

    # --- Step 5: Fraud Detection ---
    fraud_result = FraudDetectionResult()
    step_start = time.time()
    try:
        fraud_result = detect_fraud(request, policy)
        step = TraceStep(
            step_name="fraud_detection",
            status=StepStatus.PASSED,
            started_at=datetime.utcnow(),
            duration_ms=int((time.time() - step_start) * 1000),
            input_summary={
                "claims_history_count": len(request.claims_history),
                "claimed_amount": request.claimed_amount,
            },
            output_summary={
                "requires_manual_review": fraud_result.requires_manual_review,
                "signals_count": len(fraud_result.signals),
            },
            checks_performed=fraud_result.checks,
        )
        trace_steps.append(step)

    except Exception as e:
        trace_steps.append(_error_step("fraud_detection", str(e), step_start))
        component_failures.append(f"Fraud detection failed: {str(e)}")

    # --- Step 6: Decision Aggregation ---
    step_start = time.time()
    final_decision = aggregate_decision(
        claim_id=claim_id,
        request=request,
        policy_result=policy_result,
        fraud_result=fraud_result,
        extracted_data=extracted_data,
        trace_steps=trace_steps,
        component_failures=component_failures,
    )

    # Update trace with total duration
    if final_decision.trace:
        total_ms = sum(s.duration_ms for s in trace_steps)
        final_decision.trace.total_duration_ms = total_ms

    return final_decision


def _build_halt_decision(
    claim_id: str,
    request: ClaimRequest,
    error_message: str | None,
    trace_steps: list[TraceStep],
    status: TraceStatus,
) -> ClaimDecision:
    """Build a decision for early-halted claims (document issues)."""
    trace = ClaimTrace(
        claim_id=claim_id,
        timestamp=datetime.utcnow(),
        member_id=request.member_id,
        claim_category=request.claim_category.value,
        status=status,
        steps=trace_steps,
        final_decision=None,
        total_duration_ms=sum(s.duration_ms for s in trace_steps),
        error_message=error_message,
    )

    return ClaimDecision(
        claim_id=claim_id,
        decision=None,
        error_message=error_message,
        confidence_score=0.0,
        explanation=f"Claim processing halted: {error_message}",
        trace=trace,
    )


def _error_step(step_name: str, error: str, start_time: float) -> TraceStep:
    """Build a trace step for a failed component."""
    return TraceStep(
        step_name=step_name,
        status=StepStatus.ERROR,
        started_at=datetime.utcnow(),
        duration_ms=int((time.time() - start_time) * 1000),
        error_details=error,
        confidence_impact=-0.2,
        notes=[f"Component failed: {error}"],
    )


def _build_partial_extraction(request: ClaimRequest) -> ExtractedClaimData:
    """Build partial extraction from available document content when extraction fails."""
    from app.models.claim import ExtractedDocumentData, ExtractedLineItem

    documents = []
    for doc in request.documents:
        if doc.content:
            content = doc.content
            line_items = [
                ExtractedLineItem(description=item.get("description", ""), amount=item.get("amount", 0))
                for item in content.get("line_items", [])
            ]
            documents.append(ExtractedDocumentData(
                document_type=doc.actual_type or DocumentType.PRESCRIPTION,
                file_id=doc.file_id,
                patient_name=content.get("patient_name"),
                doctor_name=content.get("doctor_name"),
                diagnosis=content.get("diagnosis"),
                treatment=content.get("treatment"),
                hospital_name=content.get("hospital_name"),
                line_items=line_items,
                total_amount=content.get("total"),
                confidence=0.6,
                extraction_notes=["Partial extraction from available content (component failure recovery)."],
            ))

    result = ExtractedClaimData(documents=documents, overall_confidence=0.6)

    # Populate primary fields
    for doc in result.documents:
        if doc.diagnosis and not result.primary_diagnosis:
            result.primary_diagnosis = doc.diagnosis
        if doc.patient_name and not result.primary_patient_name:
            result.primary_patient_name = doc.patient_name
        if doc.hospital_name and not result.hospital_name:
            result.hospital_name = doc.hospital_name
        if doc.total_amount and not result.total_billed_amount:
            result.total_billed_amount = doc.total_amount

    if not result.hospital_name and request.hospital_name:
        result.hospital_name = request.hospital_name

    return result
