"""Extraction Validation Agent — post-extraction coherence checks.

Runs AFTER the extraction agent (which has populated per-document fields)
and BEFORE policy engine / fraud detection.

Catches three failure modes the upstream gates miss:
  A1. Patient-name mismatch across documents (using extracted per-doc names).
  A2. Missing category-mandatory extracted fields (e.g. CONSULTATION needs a diagnosis).
  A3. Date-proximity mismatch between prescription and bill.

On any failure the result is marked as not-passed; the decision aggregator
uses this to force MANUAL_REVIEW (never to reject outright — these are
soft signals about document coherence, not policy violations).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.claim import (
    ClaimRequest,
    ClaimCategory,
    Check,
    ExtractedClaimData,
    ExtractedDocumentData,
)


# Maximum days allowed between the earliest and latest dated extracted document.
# Prescription should be on/before the bill, within this window.
DATE_PROXIMITY_MAX_DAYS = 30

# Per-category fields that MUST be present in extracted_data for an auto-decision.
# Missing any -> route to MANUAL_REVIEW.
CATEGORY_REQUIRED_FIELDS: dict[ClaimCategory, list[str]] = {
    ClaimCategory.CONSULTATION: ["primary_diagnosis", "primary_patient_name", "total_billed_amount"],
    ClaimCategory.DIAGNOSTIC:   ["primary_patient_name", "total_billed_amount"],
    ClaimCategory.PHARMACY:     ["primary_patient_name", "total_billed_amount"],
    ClaimCategory.DENTAL:       ["primary_diagnosis", "primary_patient_name", "total_billed_amount"],
    ClaimCategory.VISION:       ["primary_patient_name", "total_billed_amount"],
    ClaimCategory.ALTERNATIVE_MEDICINE: ["primary_diagnosis", "primary_patient_name", "total_billed_amount"],
}


class ExtractionValidationResult:
    def __init__(self) -> None:
        self.passed: bool = True
        self.flags: list[str] = []
        self.checks: list[Check] = []


def validate_extraction(
    request: ClaimRequest,
    extracted_data: ExtractedClaimData,
) -> ExtractionValidationResult:
    """Run post-extraction coherence checks.

    Never halts the pipeline. Failures are surfaced as flags that the
    decision aggregator translates into MANUAL_REVIEW.
    """
    result = ExtractionValidationResult()

    name_check = _check_patient_name_consistency(extracted_data)
    result.checks.append(name_check)
    if name_check.result == "FAIL":
        result.passed = False
        result.flags.append(name_check.details)

    date_check = _check_date_proximity(extracted_data)
    result.checks.append(date_check)
    if date_check.result == "FAIL":
        result.passed = False
        result.flags.append(date_check.details)

    fields_check = _check_category_required_fields(request, extracted_data)
    result.checks.append(fields_check)
    if fields_check.result == "FAIL":
        result.passed = False
        result.flags.append(fields_check.details)

    return result


# ---------------------------------------------------------------------------
# A1: Patient-name consistency across extracted documents
# ---------------------------------------------------------------------------

def _check_patient_name_consistency(extracted: ExtractedClaimData) -> Check:
    named_docs = [d for d in extracted.documents if d.patient_name and d.patient_name.strip()]

    if len(named_docs) < 2:
        # Cannot cross-validate. Note this explicitly so reviewers know it's a
        # weak pass, not a strong one.
        return Check(
            check_name="extracted_patient_name_consistency",
            result="PASS",
            details=(
                f"Only {len(named_docs)} of {len(extracted.documents)} document(s) "
                f"had an extracted patient name — cross-validation skipped."
            ),
            relevant_policy_rule="All claim documents must belong to the same patient.",
        )

    normalized = {_normalize_name(d.patient_name): d for d in named_docs}
    if len(normalized) > 1:
        per_doc = "; ".join(
            f"{d.document_type.value}='{d.patient_name}'" for d in named_docs
        )
        return Check(
            check_name="extracted_patient_name_consistency",
            result="FAIL",
            details=(
                f"Patient names extracted from documents do not match. {per_doc}. "
                f"All documents in a claim must belong to the same patient."
            ),
            relevant_policy_rule="All claim documents must belong to the same patient.",
        )

    return Check(
        check_name="extracted_patient_name_consistency",
        result="PASS",
        details=f"All {len(named_docs)} document(s) reference the same patient: '{named_docs[0].patient_name}'.",
        relevant_policy_rule="",
    )


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


# ---------------------------------------------------------------------------
# A3: Date proximity between extracted documents
# ---------------------------------------------------------------------------

def _check_date_proximity(extracted: ExtractedClaimData) -> Check:
    dated_docs: list[tuple[ExtractedDocumentData, datetime]] = []
    for d in extracted.documents:
        parsed = _parse_date(d.date)
        if parsed is not None:
            dated_docs.append((d, parsed))

    if len(dated_docs) < 2:
        return Check(
            check_name="document_date_proximity",
            result="PASS",
            details=(
                f"Only {len(dated_docs)} of {len(extracted.documents)} document(s) "
                f"had an extractable date — proximity check skipped."
            ),
            relevant_policy_rule=f"Documents in a single claim should be within {DATE_PROXIMITY_MAX_DAYS} days.",
        )

    earliest = min(dated_docs, key=lambda x: x[1])
    latest = max(dated_docs, key=lambda x: x[1])
    delta_days = (latest[1] - earliest[1]).days

    if delta_days > DATE_PROXIMITY_MAX_DAYS:
        return Check(
            check_name="document_date_proximity",
            result="FAIL",
            details=(
                f"Documents span {delta_days} days "
                f"({earliest[0].document_type.value} on {earliest[0].date} -> "
                f"{latest[0].document_type.value} on {latest[0].date}), exceeding the "
                f"{DATE_PROXIMITY_MAX_DAYS}-day window. Documents may belong to different encounters."
            ),
            relevant_policy_rule=f"Documents in a single claim should be within {DATE_PROXIMITY_MAX_DAYS} days.",
        )

    return Check(
        check_name="document_date_proximity",
        result="PASS",
        details=f"All dated documents fall within {delta_days} day(s) of each other.",
        relevant_policy_rule="",
    )


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# A2: Category-mandatory extracted fields
# ---------------------------------------------------------------------------

def _check_category_required_fields(
    request: ClaimRequest,
    extracted: ExtractedClaimData,
) -> Check:
    required = CATEGORY_REQUIRED_FIELDS.get(request.claim_category, [])
    if not required:
        return Check(
            check_name="category_required_fields",
            result="PASS",
            details=f"No category-specific extraction requirements for {request.claim_category.value}.",
            relevant_policy_rule="",
        )

    missing: list[str] = []
    for field in required:
        value = getattr(extracted, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)

    if missing:
        return Check(
            check_name="category_required_fields",
            result="FAIL",
            details=(
                f"{request.claim_category.value} claim is missing required extracted field(s): "
                f"{', '.join(missing)}. Cannot auto-decide; routing to manual review."
            ),
            relevant_policy_rule=f"Category {request.claim_category.value} requires {required}.",
        )

    return Check(
        check_name="category_required_fields",
        result="PASS",
        details=f"All required fields for {request.claim_category.value} present in extracted data.",
        relevant_policy_rule="",
    )
