"""Deterministic policy engine — applies all policy rules without LLM.

This is the core decision-making component. It takes extracted claim data
and policy terms, then produces a decision based purely on rule evaluation.
No LLM is used here — financial calculations must be predictable and testable.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from app.models.claim import (
    ClaimRequest,
    ExtractedClaimData,
    Decision,
    PolicyCheckResult,
    LineItemDecision,
    ClaimCategory,
)
from app.models.policy import PolicyTerms, OPDCategory


class PolicyEngineResult:
    """Result from the policy engine evaluation."""

    def __init__(self):
        self.decision: Optional[Decision] = None
        self.approved_amount: Optional[float] = None
        self.rejection_reasons: list[str] = []
        self.checks: list[PolicyCheckResult] = []
        self.line_item_decisions: list[LineItemDecision] = []
        self.explanation_parts: list[str] = []
        self.requires_manual_review: bool = False


def evaluate_claim(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
) -> PolicyEngineResult:
    """Run all policy checks and produce a decision.

    Checks are applied in order:
    1. Member eligibility
    2. Submission rules (deadline, minimum amount)
    3. Waiting period
    4. Exclusions
    5. Pre-authorization requirements
    6. Per-claim limit
    7. Sub-limit & annual limit
    8. Line-item level coverage (dental/vision exclusions)
    9. Network discount + co-pay calculation
    """
    result = PolicyEngineResult()
    category_key = request.claim_category.value.lower()
    category_config = policy.opd_categories.get(category_key)

    # --- Check 1: Category covered ---
    if category_config is None or not category_config.covered:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("CATEGORY_NOT_COVERED")
        result.checks.append(PolicyCheckResult(
            check_name="category_coverage",
            passed=False,
            details=f"Category '{request.claim_category.value}' is not covered under this policy.",
            policy_rule="opd_categories",
        ))
        return result

    result.checks.append(PolicyCheckResult(
        check_name="category_coverage",
        passed=True,
        details=f"Category '{request.claim_category.value}' is covered.",
        policy_rule="opd_categories",
    ))

    # --- Check 2: Submission deadline ---
    deadline_check = _check_submission_deadline(request, policy)
    result.checks.append(deadline_check)
    if not deadline_check.passed:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("SUBMISSION_DEADLINE_EXCEEDED")
        return result

    # --- Check 3: Minimum claim amount ---
    min_amount_check = _check_minimum_amount(request, policy)
    result.checks.append(min_amount_check)
    if not min_amount_check.passed:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("BELOW_MINIMUM_AMOUNT")
        return result

    # --- Check 4: Exclusions (checked before waiting period) ---
    exclusion_check = _check_exclusions(request, extracted_data, policy)
    result.checks.append(exclusion_check)
    if not exclusion_check.passed:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("EXCLUDED_CONDITION")
        result.explanation_parts.append(exclusion_check.details)
        return result

    # --- Check 5: Waiting period ---
    waiting_check = _check_waiting_period(request, extracted_data, policy)
    result.checks.append(waiting_check)
    if not waiting_check.passed:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("WAITING_PERIOD")
        result.explanation_parts.append(waiting_check.details)
        return result

    # --- Check 6: Pre-authorization ---
    pre_auth_check = _check_pre_authorization(request, extracted_data, policy, category_config)
    result.checks.append(pre_auth_check)
    if not pre_auth_check.passed:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("PRE_AUTH_MISSING")
        result.explanation_parts.append(pre_auth_check.details)
        return result

    # --- Check 7: Line-item level coverage (for dental/vision) ---
    line_item_decisions = _evaluate_line_items(request, extracted_data, policy, category_config)
    result.line_item_decisions = line_item_decisions

    # --- Check 8: Per-claim limit ---
    # For categories with line-item filtering, check the approvable amount, not claimed total.
    # Effective limit = max(global per_claim_limit, category sub_limit) to allow
    # categories like dental (sub_limit=10000) to exceed the base per_claim_limit (5000).
    approvable_amount = (
        sum(lid.amount for lid in line_item_decisions if lid.approved)
        if line_item_decisions
        else request.claimed_amount
    )
    effective_limit = max(policy.coverage.per_claim_limit, category_config.sub_limit)
    per_claim_check = _check_per_claim_limit(request, policy, effective_limit, approvable_amount)
    result.checks.append(per_claim_check)
    if not per_claim_check.passed:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("PER_CLAIM_EXCEEDED")
        result.explanation_parts.append(per_claim_check.details)
        return result

    # --- Check 9: Calculate approved amount ---
    approved_amount = _calculate_approved_amount(
        request, extracted_data, policy, category_config, line_item_decisions
    )
    result.approved_amount = approved_amount

    # --- Check 10: Sub-limit (informational — per-claim limit is the hard cap) ---
    sub_limit_check = _check_sub_limit(approved_amount, category_config, request)
    result.checks.append(sub_limit_check)
    # Note: Sub-limit is informational. The per-claim limit (max of global and category)
    # is the hard cap. Sub-limit is not re-applied after discount/copay calculation.

    # --- Check 11: Annual OPD limit ---
    annual_check = _check_annual_limit(request, approved_amount, policy)
    result.checks.append(annual_check)
    if not annual_check.passed:
        remaining = policy.coverage.annual_opd_limit - request.ytd_claims_amount
        approved_amount = min(approved_amount, max(0, remaining))
        result.approved_amount = approved_amount

    # --- Determine final decision ---
    if line_item_decisions and any(not lid.approved for lid in line_item_decisions):
        if any(lid.approved for lid in line_item_decisions):
            result.decision = Decision.PARTIAL
        else:
            result.decision = Decision.REJECTED
            result.rejection_reasons.append("ALL_ITEMS_EXCLUDED")
    elif approved_amount <= 0:
        result.decision = Decision.REJECTED
        result.rejection_reasons.append("ZERO_APPROVED_AMOUNT")
    elif approved_amount < request.claimed_amount and not line_item_decisions:
        # Amount was capped by limits
        result.decision = Decision.APPROVED
    else:
        result.decision = Decision.APPROVED

    return result


# --- Individual Check Functions ---


def _check_submission_deadline(request: ClaimRequest, policy: PolicyTerms) -> PolicyCheckResult:
    """Check if claim was submitted within deadline from treatment date.

    Note: We use the treatment_date as a proxy. In production, we'd compare
    against the actual submission timestamp. For evaluation purposes, we assume
    the claim is submitted on the same day or shortly after treatment.
    """
    deadline_days = policy.submission_rules.deadline_days_from_treatment
    # In a real system, we'd compare submission_date vs treatment_date.
    # Since we don't have a separate submission_date field, we assume timely submission.
    return PolicyCheckResult(
        check_name="submission_deadline",
        passed=True,
        details=f"Claim assumed submitted within {deadline_days}-day deadline of treatment date {request.treatment_date}.",
        policy_rule=f"submission_rules.deadline_days_from_treatment = {deadline_days}",
    )


def _check_minimum_amount(request: ClaimRequest, policy: PolicyTerms) -> PolicyCheckResult:
    """Check if claim meets minimum amount."""
    min_amount = policy.submission_rules.minimum_claim_amount
    passed = request.claimed_amount >= min_amount
    return PolicyCheckResult(
        check_name="minimum_claim_amount",
        passed=passed,
        details=f"Claimed ₹{request.claimed_amount}. Minimum: ₹{min_amount}.",
        policy_rule=f"submission_rules.minimum_claim_amount = {min_amount}",
    )


def _check_waiting_period(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
) -> PolicyCheckResult:
    """Check if claim falls within any waiting period."""
    from app.policy.loader import get_member

    member = get_member(policy, request.member_id)
    if not member or not member.join_date:
        return PolicyCheckResult(
            check_name="waiting_period",
            passed=True,
            details="No join date available for waiting period check.",
            policy_rule="waiting_periods",
        )

    join_date = _parse_date(member.join_date)
    treatment_date = _parse_date(request.treatment_date)
    days_since_join = (treatment_date - join_date).days

    # Check initial waiting period
    initial_days = policy.waiting_periods.initial_waiting_period_days
    if days_since_join < initial_days:
        eligible_date = join_date.replace(day=join_date.day) + _timedelta(days=initial_days)
        return PolicyCheckResult(
            check_name="waiting_period",
            passed=False,
            details=(
                f"Member joined on {member.join_date}. Treatment on {request.treatment_date} "
                f"is within the {initial_days}-day initial waiting period. "
                f"Member will be eligible from {eligible_date.isoformat()}."
            ),
            policy_rule=f"waiting_periods.initial_waiting_period_days = {initial_days}",
        )

    # Check condition-specific waiting periods
    diagnosis = (extracted_data.primary_diagnosis or "").lower()
    for condition, days in policy.waiting_periods.specific_conditions.items():
        if _condition_matches_diagnosis(condition, diagnosis):
            if days_since_join < days:
                eligible_date = join_date + _timedelta(days=days)
                return PolicyCheckResult(
                    check_name="waiting_period",
                    passed=False,
                    details=(
                        f"Member joined on {member.join_date}. Treatment on {request.treatment_date} "
                        f"is within the {days}-day waiting period for '{condition}'. "
                        f"Member will be eligible for {condition}-related claims from {eligible_date.isoformat()}."
                    ),
                    policy_rule=f"waiting_periods.specific_conditions.{condition} = {days}",
                )

    return PolicyCheckResult(
        check_name="waiting_period",
        passed=True,
        details=f"No applicable waiting period. Member joined {member.join_date}, {days_since_join} days ago.",
        policy_rule="waiting_periods",
    )


def _check_exclusions(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
) -> PolicyCheckResult:
    """Check if the diagnosis or treatment is excluded."""
    diagnosis = (extracted_data.primary_diagnosis or "").lower()
    treatment = ""
    for doc in extracted_data.documents:
        if doc.treatment:
            treatment = doc.treatment.lower()
            break

    combined_text = f"{diagnosis} {treatment}"

    # Check general exclusions
    for exclusion in policy.exclusions.conditions:
        if _exclusion_matches(exclusion, combined_text):
            return PolicyCheckResult(
                check_name="exclusion_check",
                passed=False,
                details=f"Treatment/diagnosis matches exclusion: '{exclusion}'. This is not covered under the policy.",
                policy_rule=f"exclusions.conditions: '{exclusion}'",
            )

    return PolicyCheckResult(
        check_name="exclusion_check",
        passed=True,
        details="No exclusions matched.",
        policy_rule="exclusions",
    )


def _check_pre_authorization(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
    category_config: OPDCategory,
) -> PolicyCheckResult:
    """Check if pre-authorization was required and obtained."""
    # Check if any high-value tests require pre-auth
    if category_config.high_value_tests_requiring_pre_auth:
        threshold = category_config.pre_auth_threshold or 0
        tests_in_claim = _get_tests_in_claim(extracted_data)

        for test in category_config.high_value_tests_requiring_pre_auth:
            if _test_matches_claim(test, tests_in_claim, extracted_data):
                if request.claimed_amount > threshold:
                    return PolicyCheckResult(
                        check_name="pre_authorization",
                        passed=False,
                        details=(
                            f"Pre-authorization is required for {test} when amount exceeds "
                            f"₹{threshold:,.0f}. Claimed amount: ₹{request.claimed_amount:,.0f}. "
                            f"Please obtain pre-authorization and resubmit the claim."
                        ),
                        policy_rule=f"diagnostic.high_value_tests_requiring_pre_auth: {test}, threshold: {threshold}",
                    )

    # Check auto_manual_review_above threshold (for general pre-auth)
    if request.claimed_amount > policy.fraud_thresholds.auto_manual_review_above:
        # This is handled in fraud detection, not as rejection
        pass

    return PolicyCheckResult(
        check_name="pre_authorization",
        passed=True,
        details="No pre-authorization required for this claim.",
        policy_rule="pre_authorization",
    )


def _check_per_claim_limit(request: ClaimRequest, policy: PolicyTerms, effective_limit: float = None, approvable_amount: float = None) -> PolicyCheckResult:
    """Check if claimed amount exceeds per-claim limit.

    Uses the approvable_amount (after line-item filtering) if provided,
    otherwise uses the raw claimed_amount.
    """
    per_claim_limit = effective_limit or policy.coverage.per_claim_limit
    check_amount = approvable_amount if approvable_amount is not None else request.claimed_amount
    passed = check_amount <= per_claim_limit
    return PolicyCheckResult(
        check_name="per_claim_limit",
        passed=passed,
        details=(
            f"Claimed amount ₹{request.claimed_amount:,.0f} (approvable: ₹{check_amount:,.0f}) exceeds the per-claim limit of "
            f"₹{per_claim_limit:,.0f}. Maximum allowed per claim is ₹{per_claim_limit:,.0f}."
            if not passed else
            f"Approvable amount ₹{check_amount:,.0f} is within per-claim limit of ₹{per_claim_limit:,.0f}."
        ),
        policy_rule=f"coverage.per_claim_limit = {per_claim_limit}",
    )


def _check_sub_limit(amount: float, category_config: OPDCategory, request: ClaimRequest) -> PolicyCheckResult:
    """Check if amount exceeds category sub-limit."""
    sub_limit = category_config.sub_limit
    passed = amount <= sub_limit
    return PolicyCheckResult(
        check_name="sub_limit",
        passed=passed,
        details=(
            f"Amount ₹{amount:,.0f} exceeds category sub-limit of ₹{sub_limit:,.0f}. Capped at ₹{sub_limit:,.0f}."
            if not passed else
            f"Amount ₹{amount:,.0f} is within category sub-limit of ₹{sub_limit:,.0f}."
        ),
        policy_rule=f"opd_categories.{request.claim_category.value.lower()}.sub_limit = {sub_limit}",
    )


def _check_annual_limit(request: ClaimRequest, approved_amount: float, policy: PolicyTerms) -> PolicyCheckResult:
    """Check if claim would exceed annual OPD limit."""
    annual_limit = policy.coverage.annual_opd_limit
    total_after = request.ytd_claims_amount + approved_amount
    passed = total_after <= annual_limit
    remaining = annual_limit - request.ytd_claims_amount
    return PolicyCheckResult(
        check_name="annual_opd_limit",
        passed=passed,
        details=(
            f"YTD claims: ₹{request.ytd_claims_amount:,.0f}. This claim: ₹{approved_amount:,.0f}. "
            f"Annual limit: ₹{annual_limit:,.0f}. Remaining: ₹{max(0, remaining):,.0f}."
        ),
        policy_rule=f"coverage.annual_opd_limit = {annual_limit}",
    )


# --- Line Item Evaluation ---


def _evaluate_line_items(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
    category_config: OPDCategory,
) -> list[LineItemDecision]:
    """Evaluate individual line items for dental/vision exclusions."""
    decisions = []

    # Get line items from extracted data
    line_items = []
    for doc in extracted_data.documents:
        line_items.extend(doc.line_items)

    if not line_items:
        return []

    # For dental claims — check covered/excluded procedures
    if request.claim_category == ClaimCategory.DENTAL:
        for item in line_items:
            desc_lower = item.description.lower()
            is_excluded = any(
                exc.lower() in desc_lower or desc_lower in exc.lower()
                for exc in category_config.excluded_procedures
            )
            is_covered = any(
                cov.lower() in desc_lower or desc_lower in cov.lower()
                for cov in category_config.covered_procedures
            )

            if is_excluded:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=False,
                    reason=f"'{item.description}' is an excluded cosmetic/dental procedure.",
                ))
            elif is_covered or not category_config.covered_procedures:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=True,
                    reason="Covered procedure.",
                ))
            else:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=True,
                    reason="Not explicitly excluded.",
                ))

    # For vision claims — check covered/excluded items
    elif request.claim_category == ClaimCategory.VISION:
        for item in line_items:
            desc_lower = item.description.lower()
            is_excluded = any(
                exc.lower() in desc_lower or desc_lower in exc.lower()
                for exc in category_config.excluded_items
            )
            if is_excluded:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=False,
                    reason=f"'{item.description}' is an excluded item.",
                ))
            else:
                decisions.append(LineItemDecision(
                    description=item.description,
                    amount=item.amount,
                    approved=True,
                    reason="Covered item.",
                ))

    return decisions


# --- Amount Calculation ---


def _calculate_approved_amount(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
    category_config: OPDCategory,
    line_item_decisions: list[LineItemDecision],
) -> float:
    """Calculate the final approved amount after discounts and co-pay.

    Order: base amount → line-item filtering → network discount → co-pay deduction
    """
    # Start with claimed amount or sum of approved line items
    if line_item_decisions:
        base_amount = sum(lid.amount for lid in line_item_decisions if lid.approved)
    else:
        base_amount = request.claimed_amount

    # Apply network discount (if applicable)
    amount_after_discount = base_amount
    is_network = _is_network_hospital(request, extracted_data, policy)
    if is_network and category_config.network_discount_percent > 0:
        discount = base_amount * (category_config.network_discount_percent / 100)
        amount_after_discount = base_amount - discount

    # Apply co-pay
    copay_percent = category_config.copay_percent
    if copay_percent > 0:
        copay_amount = amount_after_discount * (copay_percent / 100)
        final_amount = amount_after_discount - copay_amount
    else:
        final_amount = amount_after_discount

    return round(final_amount, 2)


# --- Helper Functions ---


def _is_network_hospital(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
    policy: PolicyTerms,
) -> bool:
    """Check if the hospital is in the network list."""
    hospital_name = request.hospital_name or extracted_data.hospital_name or ""
    if not hospital_name:
        return False
    hospital_lower = hospital_name.lower()
    return any(nh.lower() in hospital_lower or hospital_lower in nh.lower()
               for nh in policy.network_hospitals)


def _condition_matches_diagnosis(condition: str, diagnosis: str) -> bool:
    """Check if a waiting period condition matches the diagnosis."""
    condition_lower = condition.lower()
    diagnosis_lower = diagnosis.lower()

    # Direct and common alias mappings
    mappings = {
        "diabetes": ["diabetes", "t2dm", "type 2 diabetes", "diabetic", "metformin", "glimepiride"],
        "hypertension": ["hypertension", "htn", "high blood pressure"],
        "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid"],
        "joint_replacement": ["joint replacement", "knee replacement", "hip replacement"],
        "maternity": ["maternity", "pregnancy", "prenatal"],
        "mental_health": ["mental health", "depression", "anxiety", "psychiatric"],
        "obesity_treatment": ["obesity", "bariatric", "weight loss", "bmi"],
        "hernia": ["inguinal hernia", "umbilical hernia", "hiatal hernia", "incisional hernia", "femoral hernia"],
        "cataract": ["cataract"],
    }

    keywords = mappings.get(condition_lower, [condition_lower])
    return any(kw in diagnosis_lower for kw in keywords)


def _exclusion_matches(exclusion: str, combined_text: str) -> bool:
    """Check if an exclusion matches the claim text."""
    exclusion_lower = exclusion.lower()

    # Map exclusion phrases to keywords for matching
    keyword_mappings = {
        "obesity and weight loss programs": ["obesity", "weight loss", "bariatric", "bmi 3", "bmi 4", "morbid obesity", "diet program", "diet plan"],
        "bariatric surgery": ["bariatric"],
        "cosmetic or aesthetic procedures": ["cosmetic", "aesthetic", "whitening", "bleaching"],
        "substance abuse treatment": ["substance abuse", "alcohol addiction", "drug addiction"],
        "experimental treatments": ["experimental"],
        "infertility and assisted reproduction": ["infertility", "ivf", "assisted reproduction"],
        "self-inflicted injuries": ["self-inflicted", "self inflicted"],
        "health supplements and tonics": ["supplement", "tonic"],
        "vaccination (non-medically necessary)": ["vaccination"],
    }

    keywords = keyword_mappings.get(exclusion_lower, [exclusion_lower.split("(")[0].strip()])
    return any(kw in combined_text for kw in keywords)


def _get_tests_in_claim(extracted_data: ExtractedClaimData) -> list[str]:
    """Get all tests mentioned in the claim documents."""
    tests = []
    for doc in extracted_data.documents:
        tests.extend(doc.tests_ordered)
        for item in doc.line_items:
            tests.append(item.description)
    return tests


def _test_matches_claim(test_name: str, tests_in_claim: list[str], extracted_data: ExtractedClaimData) -> bool:
    """Check if a specific test type is present in the claim."""
    test_lower = test_name.lower()
    for t in tests_in_claim:
        if test_lower in t.lower():
            return True
    # Also check diagnosis/treatment fields
    for doc in extracted_data.documents:
        if doc.treatment and test_lower in doc.treatment.lower():
            return True
    return False


def _parse_date(date_str: str) -> date:
    """Parse a date string in common formats."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def _timedelta(days: int):
    """Create a timedelta."""
    from datetime import timedelta
    return timedelta(days=days)
