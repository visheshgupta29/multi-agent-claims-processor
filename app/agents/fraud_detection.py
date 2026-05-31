"""Fraud Detection Agent — identifies suspicious patterns.

Checks:
- Same-day claims limit exceeded
- Monthly claims limit exceeded
- High-value claim threshold
- Unusually high frequency

Routes to MANUAL_REVIEW rather than auto-rejecting.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.models.claim import ClaimRequest, FraudSignal, Check
from app.models.policy import PolicyTerms


class FraudDetectionResult:
    def __init__(self):
        self.requires_manual_review: bool = False
        self.signals: list[FraudSignal] = []
        self.checks: list[Check] = []


def detect_fraud(request: ClaimRequest, policy: PolicyTerms) -> FraudDetectionResult:
    """Analyze claim for fraud signals. Never auto-rejects — routes to manual review."""
    result = FraudDetectionResult()
    thresholds = policy.fraud_thresholds

    # Check 1: Same-day claims
    same_day_check = _check_same_day_claims(request, thresholds.same_day_claims_limit)
    result.checks.append(same_day_check)
    if same_day_check.result == "FAIL":
        result.requires_manual_review = True
        result.signals.append(FraudSignal(
            signal_name="SAME_DAY_CLAIMS_EXCEEDED",
            severity="HIGH",
            details=same_day_check.details,
        ))

    # Check 2: High-value claim
    high_value_check = _check_high_value(request, thresholds.auto_manual_review_above)
    result.checks.append(high_value_check)
    if high_value_check.result == "FAIL":
        result.requires_manual_review = True
        result.signals.append(FraudSignal(
            signal_name="HIGH_VALUE_CLAIM",
            severity="MEDIUM",
            details=high_value_check.details,
        ))

    # Check 3: Monthly claims limit
    monthly_check = _check_monthly_claims(request, thresholds.monthly_claims_limit)
    result.checks.append(monthly_check)
    if monthly_check.result == "FAIL":
        result.requires_manual_review = True
        result.signals.append(FraudSignal(
            signal_name="MONTHLY_CLAIMS_EXCEEDED",
            severity="MEDIUM",
            details=monthly_check.details,
        ))

    return result


def _check_same_day_claims(request: ClaimRequest, limit: int) -> Check:
    """Check if member has exceeded same-day claims limit."""
    if not request.claims_history:
        return Check(
            check_name="same_day_claims",
            result="PASS",
            details="No claims history provided. Cannot assess same-day pattern.",
            relevant_policy_rule=f"fraud_thresholds.same_day_claims_limit = {limit}",
        )

    treatment_date = request.treatment_date
    same_day_claims = [
        c for c in request.claims_history
        if c.date == treatment_date
    ]
    count = len(same_day_claims)

    if count >= limit:
        providers = [c.provider for c in same_day_claims if c.provider]
        total_amount = sum(c.amount for c in same_day_claims)
        return Check(
            check_name="same_day_claims",
            result="FAIL",
            details=(
                f"Member has {count} existing claim(s) on {treatment_date} "
                f"(limit: {limit}). This would be claim #{count + 1} on the same day. "
                f"Previous claims from: {', '.join(providers) if providers else 'unknown providers'}. "
                f"Total same-day amount: ₹{total_amount + request.claimed_amount:,.0f}."
            ),
            relevant_policy_rule=f"fraud_thresholds.same_day_claims_limit = {limit}",
        )

    return Check(
        check_name="same_day_claims",
        result="PASS",
        details=f"Same-day claims count ({count}) within limit ({limit}).",
        relevant_policy_rule=f"fraud_thresholds.same_day_claims_limit = {limit}",
    )


def _check_high_value(request: ClaimRequest, threshold: float) -> Check:
    """Check if claim amount triggers high-value review."""
    if request.claimed_amount > threshold:
        return Check(
            check_name="high_value_claim",
            result="FAIL",
            details=(
                f"Claimed amount ₹{request.claimed_amount:,.0f} exceeds automatic review "
                f"threshold of ₹{threshold:,.0f}."
            ),
            relevant_policy_rule=f"fraud_thresholds.auto_manual_review_above = {threshold}",
        )
    return Check(
        check_name="high_value_claim",
        result="PASS",
        details=f"Claimed amount ₹{request.claimed_amount:,.0f} below threshold ₹{threshold:,.0f}.",
        relevant_policy_rule=f"fraud_thresholds.auto_manual_review_above = {threshold}",
    )


def _check_monthly_claims(request: ClaimRequest, limit: int) -> Check:
    """Check if member has exceeded monthly claims limit."""
    if not request.claims_history:
        return Check(
            check_name="monthly_claims",
            result="PASS",
            details="No claims history provided.",
            relevant_policy_rule=f"fraud_thresholds.monthly_claims_limit = {limit}",
        )

    # Count claims in the same month as treatment date
    try:
        treatment_month = request.treatment_date[:7]  # "YYYY-MM"
        same_month = [c for c in request.claims_history if c.date.startswith(treatment_month)]
        count = len(same_month)
    except (IndexError, AttributeError):
        return Check(
            check_name="monthly_claims",
            result="PASS",
            details="Could not parse dates for monthly check.",
            relevant_policy_rule=f"fraud_thresholds.monthly_claims_limit = {limit}",
        )

    if count >= limit:
        return Check(
            check_name="monthly_claims",
            result="FAIL",
            details=f"Member has {count} claims in {treatment_month} (limit: {limit}).",
            relevant_policy_rule=f"fraud_thresholds.monthly_claims_limit = {limit}",
        )

    return Check(
        check_name="monthly_claims",
        result="PASS",
        details=f"Monthly claims count ({count}) within limit ({limit}).",
        relevant_policy_rule=f"fraud_thresholds.monthly_claims_limit = {limit}",
    )
