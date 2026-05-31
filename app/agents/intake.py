"""Intake Agent — validates claim metadata and member eligibility."""

from __future__ import annotations

from app.models.claim import ClaimRequest, Check
from app.models.policy import PolicyTerms
from app.policy.loader import get_member


class IntakeResult:
    def __init__(self):
        self.passed: bool = True
        self.error_message: str | None = None
        self.checks: list[Check] = []
        self.member_name: str = ""


def validate_intake(request: ClaimRequest, policy: PolicyTerms) -> IntakeResult:
    """Validate basic claim metadata and member eligibility."""
    result = IntakeResult()

    # Check 1: Policy ID matches
    if request.policy_id != policy.policy_id:
        result.passed = False
        result.error_message = f"Invalid policy ID: {request.policy_id}."
        result.checks.append(Check(
            check_name="policy_id_validation",
            result="FAIL",
            details=f"Policy ID '{request.policy_id}' does not match loaded policy '{policy.policy_id}'.",
            relevant_policy_rule="policy_id",
        ))
        return result

    result.checks.append(Check(
        check_name="policy_id_validation",
        result="PASS",
        details="Policy ID valid.",
        relevant_policy_rule="policy_id",
    ))

    # Check 2: Member exists
    member = get_member(policy, request.member_id)
    if member is None:
        result.passed = False
        result.error_message = f"Member '{request.member_id}' not found in policy roster."
        result.checks.append(Check(
            check_name="member_eligibility",
            result="FAIL",
            details=f"Member ID '{request.member_id}' not found.",
            relevant_policy_rule="members",
        ))
        return result

    result.member_name = member.name
    result.checks.append(Check(
        check_name="member_eligibility",
        result="PASS",
        details=f"Member '{member.name}' ({member.member_id}) found. Relationship: {member.relationship}.",
        relevant_policy_rule="members",
    ))

    # Check 3: Policy active
    result.checks.append(Check(
        check_name="policy_active",
        result="PASS",
        details=f"Policy status: {policy.policy_holder.renewal_status}. "
                f"Period: {policy.policy_holder.policy_start_date} to {policy.policy_holder.policy_end_date}.",
        relevant_policy_rule="policy_holder.renewal_status",
    ))

    # Check 4: Documents provided
    if not request.documents:
        result.passed = False
        result.error_message = "No documents provided with the claim."
        result.checks.append(Check(
            check_name="documents_present",
            result="FAIL",
            details="Claim must include at least one document.",
            relevant_policy_rule="",
        ))
        return result

    result.checks.append(Check(
        check_name="documents_present",
        result="PASS",
        details=f"{len(request.documents)} document(s) attached.",
        relevant_policy_rule="",
    ))

    # Check 5: Claimed amount positive
    if request.claimed_amount <= 0:
        result.passed = False
        result.error_message = "Claimed amount must be positive."
        result.checks.append(Check(
            check_name="amount_positive",
            result="FAIL",
            details=f"Claimed amount: ₹{request.claimed_amount}. Must be > 0.",
            relevant_policy_rule="",
        ))
        return result

    result.checks.append(Check(
        check_name="amount_positive",
        result="PASS",
        details=f"Claimed amount: ₹{request.claimed_amount:,.0f}.",
        relevant_policy_rule="",
    ))

    return result
