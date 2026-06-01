"""Decision Aggregator — combines all upstream results into final ClaimDecision."""

from __future__ import annotations

from datetime import datetime

from app.models.claim import (
    ClaimRequest,
    ClaimDecision,
    ClaimTrace,
    Decision,
    TraceStep,
    TraceStatus,
    ExtractedClaimData,
)
from app.agents.policy_engine import PolicyEngineResult
from app.agents.fraud_detection import FraudDetectionResult


def aggregate_decision(
    claim_id: str,
    request: ClaimRequest,
    policy_result: PolicyEngineResult,
    fraud_result: FraudDetectionResult,
    extracted_data: ExtractedClaimData,
    trace_steps: list[TraceStep],
    component_failures: list[str] = None,
    extraction_validation_flags: list[str] = None,
) -> ClaimDecision:
    """Aggregate all results into a final claim decision.

    Priority order:
    1. Fraud signals → MANUAL_REVIEW (overrides policy decision)
    2. Policy rejection → REJECTED
    3. Policy partial → PARTIAL
    4. Policy approval → APPROVED

    Component failures reduce confidence and may recommend manual review.
    """
    component_failures = component_failures or []
    extraction_validation_flags = extraction_validation_flags or []
    review_flags: list[str] = []

    # Start with policy engine decision
    decision = policy_result.decision
    approved_amount = policy_result.approved_amount
    confidence = extracted_data.overall_confidence

    # Fraud override: if fraud signals detected, route to manual review
    if fraud_result.requires_manual_review:
        decision = Decision.MANUAL_REVIEW
        confidence = min(confidence, 0.6)

    # Extraction validation override: name mismatch, date mismatch, or
    # missing category-required fields. Only override when the policy engine
    # would otherwise auto-APPROVE — definitive REJECTED/PARTIAL outcomes
    # (with concrete line-item rationale) are still trusted. Also skipped when
    # a component already failed: the failure path drops confidence and sets
    # manual_review_recommended on its own, so we don't double-penalize.
    if (
        extraction_validation_flags
        and decision == Decision.APPROVED
        and not component_failures
    ):
        decision = Decision.MANUAL_REVIEW
        confidence = min(confidence, 0.5)
        review_flags.extend(extraction_validation_flags)

    # Data quality override: low overall extraction confidence with missing key fields.
    # Same scope rule — only override an auto-APPROVE, and not when a component failed.
    if (
        decision == Decision.APPROVED
        and not component_failures
        and _requires_manual_review_for_extraction(extracted_data)
    ):
        decision = Decision.MANUAL_REVIEW
        confidence = min(confidence, 0.5)
        review_flags.append(
            "Low extraction confidence with missing key fields (diagnosis, patient name, billed total)."
        )

    # Component failure handling
    if component_failures:
        confidence -= 0.2 * len(component_failures)
        confidence = max(confidence, 0.3)
        # If we couldn't extract data but policy says approve, still approve with low confidence
        if decision == Decision.APPROVED or decision == Decision.PARTIAL:
            pass  # Keep the decision but reduce confidence

    # Build explanation
    explanation = _build_explanation(
        decision,
        policy_result,
        fraud_result,
        approved_amount,
        component_failures,
        review_flags,
    )

    # Build the trace
    trace = ClaimTrace(
        claim_id=claim_id,
        timestamp=datetime.utcnow(),
        member_id=request.member_id,
        claim_category=request.claim_category.value,
        status=TraceStatus.COMPLETED,
        steps=trace_steps,
        final_decision=decision,
        approved_amount=approved_amount,
        confidence_score=round(confidence, 2),
    )

    return ClaimDecision(
        claim_id=claim_id,
        decision=decision,
        approved_amount=approved_amount,
        rejection_reasons=policy_result.rejection_reasons,
        confidence_score=round(confidence, 2),
        explanation=explanation,
        line_item_decisions=policy_result.line_item_decisions,
        policy_checks=policy_result.checks,
        fraud_signals=fraud_result.signals,
        manual_review_recommended=(
            fraud_result.requires_manual_review
            or len(component_failures) > 0
            or len(review_flags) > 0
        ),
        trace=trace,
    )


def _build_explanation(
    decision: Decision,
    policy_result: PolicyEngineResult,
    fraud_result: FraudDetectionResult,
    approved_amount: float | None,
    component_failures: list[str],
    review_flags: list[str],
) -> str:
    """Build a human-readable explanation of the decision."""
    parts = []

    if decision == Decision.APPROVED:
        parts.append(f"Claim APPROVED for ₹{approved_amount:,.0f}.")
        # Add co-pay/discount details from checks
        for check in policy_result.checks:
            if "co-pay" in check.details.lower() or "discount" in check.details.lower():
                parts.append(check.details)

    elif decision == Decision.PARTIAL:
        parts.append(f"Claim PARTIALLY APPROVED for ₹{approved_amount:,.0f}.")
        parts.append("Some line items were excluded:")
        for lid in policy_result.line_item_decisions:
            status = "✓ Approved" if lid.approved else "✗ Rejected"
            parts.append(f"  - {lid.description} (₹{lid.amount:,.0f}): {status} — {lid.reason}")

    elif decision == Decision.REJECTED:
        reasons = ", ".join(policy_result.rejection_reasons)
        parts.append(f"Claim REJECTED. Reason(s): {reasons}.")
        for check in policy_result.checks:
            if not check.passed:
                parts.append(f"  - {check.details}")

    elif decision == Decision.MANUAL_REVIEW:
        parts.append("Claim routed to MANUAL REVIEW.")
        for signal in fraud_result.signals:
            parts.append(f"  - [{signal.severity}] {signal.signal_name}: {signal.details}")

    if component_failures:
        parts.append("")
        parts.append("⚠ Component failures during processing:")
        for failure in component_failures:
            parts.append(f"  - {failure}")
        parts.append("Manual review is recommended due to incomplete processing.")

    if review_flags:
        parts.append("")
        parts.append("⚠ Data quality flags:")
        for flag in review_flags:
            parts.append(f"  - {flag}")

    return "\n".join(parts)


def _requires_manual_review_for_extraction(extracted_data: ExtractedClaimData) -> bool:
    """Require manual review when extraction quality is too low and key fields are missing."""
    if extracted_data.overall_confidence >= 0.6:
        return False

    missing_key_fields = 0
    if not extracted_data.primary_diagnosis:
        missing_key_fields += 1
    if not extracted_data.primary_patient_name:
        missing_key_fields += 1
    if extracted_data.total_billed_amount is None:
        missing_key_fields += 1

    return missing_key_fields >= 2
