"""Document Verification Agent — Gate node that halts the pipeline early.

Responsibilities:
1. Check that required document types are present for the claim category
2. Detect unreadable/poor quality documents
3. Cross-validate patient names across documents
4. Produce specific, actionable error messages (not generic errors)

This agent HALTS the pipeline on failure — no further processing occurs.
"""

from __future__ import annotations

from typing import Optional

from app.models.claim import (
    ClaimRequest,
    DocumentInput,
    DocumentType,
    DocumentQuality,
    ClaimCategory,
    TraceStep,
    StepStatus,
    Check,
)
from app.models.policy import PolicyTerms, DocumentRequirements


class DocumentVerificationResult:
    """Result of document verification."""

    def __init__(self):
        self.passed: bool = True
        self.halt: bool = False
        self.error_message: Optional[str] = None
        self.checks: list[Check] = []
        self.notes: list[str] = []


def verify_documents(
    request: ClaimRequest,
    policy: PolicyTerms,
) -> DocumentVerificationResult:
    """Verify documents before any claim processing.

    Returns a result that either passes (continue pipeline)
    or halts with a specific user-facing error message.
    """
    result = DocumentVerificationResult()

    # Get required documents for this claim category
    category_key = request.claim_category.value
    doc_requirements = policy.document_requirements.get(category_key)

    if doc_requirements is None:
        result.passed = True
        result.checks.append(Check(
            check_name="document_requirements_lookup",
            result="PASS",
            details=f"No specific document requirements defined for category {category_key}.",
            relevant_policy_rule="document_requirements",
        ))
        return result

    # --- Check 1: Required document types present ---
    completeness_result = _check_document_completeness(
        request.documents, doc_requirements, category_key
    )
    result.checks.append(completeness_result)
    if completeness_result.result == "FAIL":
        result.passed = False
        result.halt = True
        result.error_message = completeness_result.details
        return result

    # --- Check 2: Document quality ---
    quality_result = _check_document_quality(request.documents)
    result.checks.append(quality_result)
    if quality_result.result == "FAIL":
        result.passed = False
        result.halt = True
        result.error_message = quality_result.details
        return result

    # --- Check 3: Patient name consistency across documents ---
    name_result = _check_patient_name_consistency(request.documents)
    result.checks.append(name_result)
    if name_result.result == "FAIL":
        result.passed = False
        result.halt = True
        result.error_message = name_result.details
        return result

    return result


def _check_document_completeness(
    documents: list[DocumentInput],
    requirements: DocumentRequirements,
    category_key: str,
) -> Check:
    """Check if all required document types are present."""
    required_types = set(requirements.required)
    provided_types = {}

    for doc in documents:
        if doc.actual_type:
            doc_type = doc.actual_type.value
            if doc_type not in provided_types:
                provided_types[doc_type] = []
            provided_types[doc_type].append(doc)

    # Find missing required types
    missing_types = required_types - set(provided_types.keys())

    if missing_types:
        # Build specific error message naming what was uploaded vs what's needed
        uploaded_types = list(provided_types.keys())
        missing_list = list(missing_types)

        # Build human-readable message
        uploaded_str = ", ".join(_humanize_doc_type(t) for t in uploaded_types)
        missing_str = ", ".join(_humanize_doc_type(t) for t in missing_list)

        error_msg = (
            f"Your {category_key.lower()} claim is missing required documents. "
            f"You uploaded: {uploaded_str}. "
            f"Missing: {missing_str}. "
            f"Please upload the following document(s) to proceed: {missing_str}."
        )

        return Check(
            check_name="document_completeness",
            result="FAIL",
            details=error_msg,
            relevant_policy_rule=f"document_requirements.{category_key}.required = {list(required_types)}",
        )

    return Check(
        check_name="document_completeness",
        result="PASS",
        details=f"All required documents present: {list(required_types)}.",
        relevant_policy_rule=f"document_requirements.{category_key}.required",
    )


def _check_document_quality(documents: list[DocumentInput]) -> Check:
    """Check if any documents are unreadable."""
    unreadable_docs = []
    for doc in documents:
        if doc.quality == DocumentQuality.UNREADABLE:
            unreadable_docs.append(doc)

    if unreadable_docs:
        doc_names = []
        for doc in unreadable_docs:
            doc_type = _humanize_doc_type(doc.actual_type.value) if doc.actual_type else "document"
            file_name = doc.file_name or doc.file_id
            doc_names.append(f"{doc_type} ({file_name})")

        docs_str = ", ".join(doc_names)
        error_msg = (
            f"The following document(s) cannot be read: {docs_str}. "
            f"The image appears to be blurry or unreadable. "
            f"Please re-upload a clear photo or scan of the document(s)."
        )

        return Check(
            check_name="document_quality",
            result="FAIL",
            details=error_msg,
            relevant_policy_rule="Document must be legible for processing.",
        )

    return Check(
        check_name="document_quality",
        result="PASS",
        details="All documents are readable.",
        relevant_policy_rule="",
    )


def _check_patient_name_consistency(documents: list[DocumentInput]) -> Check:
    """Check if documents belong to the same patient."""
    names_found: dict[str, str] = {}  # doc_type -> patient_name

    for doc in documents:
        name = doc.patient_name_on_doc
        if not name:
            # Try to get from content
            if doc.content and "patient_name" in doc.content:
                name = doc.content["patient_name"]

        if name:
            doc_type = doc.actual_type.value if doc.actual_type else doc.file_id
            names_found[doc_type] = name

    if len(names_found) < 2:
        return Check(
            check_name="patient_name_consistency",
            result="PASS",
            details="Insufficient documents with patient names to cross-validate (or names match).",
            relevant_policy_rule="",
        )

    # Check if all names are the same (case-insensitive, trimmed)
    unique_names = set(n.strip().lower() for n in names_found.values())
    if len(unique_names) > 1:
        # Names don't match — build specific error
        name_details = [f"{_humanize_doc_type(dt)}: '{name}'" for dt, name in names_found.items()]
        name_str = "; ".join(name_details)

        error_msg = (
            f"The uploaded documents appear to belong to different patients. "
            f"Names found — {name_str}. "
            f"All documents for a claim must belong to the same patient. "
            f"Please verify and re-upload the correct documents."
        )

        return Check(
            check_name="patient_name_consistency",
            result="FAIL",
            details=error_msg,
            relevant_policy_rule="All claim documents must belong to the same patient.",
        )

    return Check(
        check_name="patient_name_consistency",
        result="PASS",
        details=f"All documents reference the same patient: '{list(names_found.values())[0]}'.",
        relevant_policy_rule="",
    )


def _humanize_doc_type(doc_type: str) -> str:
    """Convert document type enum value to human-readable string."""
    mapping = {
        "PRESCRIPTION": "Prescription",
        "HOSPITAL_BILL": "Hospital Bill",
        "PHARMACY_BILL": "Pharmacy Bill",
        "LAB_REPORT": "Lab Report",
        "DIAGNOSTIC_REPORT": "Diagnostic Report",
        "DISCHARGE_SUMMARY": "Discharge Summary",
        "DENTAL_REPORT": "Dental Report",
    }
    return mapping.get(doc_type, doc_type.replace("_", " ").title())
