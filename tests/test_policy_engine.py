"""Unit tests for the deterministic policy engine.

Tests cover all test case scenarios TC004-TC012 at the policy rule level.
"""

import pytest
from app.models.claim import (
    ClaimRequest,
    ExtractedClaimData,
    ExtractedDocumentData,
    ExtractedLineItem,
    DocumentInput,
    DocumentType,
    ClaimCategory,
    Decision,
)
from app.agents.policy_engine import evaluate_claim


class TestTC004_CleanApproval:
    """TC004: Clean consultation claim — should be fully approved with 10% co-pay."""

    def test_approval_with_copay(self, policy):
        request = ClaimRequest(
            member_id="EMP001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-01",
            claimed_amount=1500,
            ytd_claims_amount=5000,
            documents=[
                DocumentInput(file_id="F007", actual_type=DocumentType.PRESCRIPTION),
                DocumentInput(file_id="F008", actual_type=DocumentType.HOSPITAL_BILL),
            ],
        )
        extracted = ExtractedClaimData(
            primary_diagnosis="Viral Fever",
            primary_patient_name="Rajesh Kumar",
            documents=[
                ExtractedDocumentData(
                    document_type=DocumentType.PRESCRIPTION,
                    file_id="F007",
                    diagnosis="Viral Fever",
                    patient_name="Rajesh Kumar",
                ),
                ExtractedDocumentData(
                    document_type=DocumentType.HOSPITAL_BILL,
                    file_id="F008",
                    total_amount=1500,
                    line_items=[
                        ExtractedLineItem(description="Consultation Fee", amount=1000),
                        ExtractedLineItem(description="CBC Test", amount=300),
                        ExtractedLineItem(description="Dengue NS1 Test", amount=200),
                    ],
                ),
            ],
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.APPROVED
        assert result.approved_amount == 1350  # 1500 - 10% co-pay = 1350

    def test_copay_calculation(self, policy):
        """Verify 10% co-pay is applied correctly."""
        request = ClaimRequest(
            member_id="EMP001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-01",
            claimed_amount=2000,
            ytd_claims_amount=0,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)],
        )
        extracted = ExtractedClaimData(primary_diagnosis="Viral Fever")

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.APPROVED
        assert result.approved_amount == 1800  # 2000 - 10% = 1800


class TestTC005_WaitingPeriod:
    """TC005: Diabetes treatment within 90-day waiting period — REJECTED."""

    def test_diabetes_waiting_period(self, policy):
        request = ClaimRequest(
            member_id="EMP005",  # Joined 2024-09-01
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-10-15",  # Only 44 days after joining
            claimed_amount=3000,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)],
        )
        extracted = ExtractedClaimData(
            primary_diagnosis="Type 2 Diabetes Mellitus",
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.REJECTED
        assert "WAITING_PERIOD" in result.rejection_reasons
        # Should mention eligibility date
        failed_check = next(c for c in result.checks if c.check_name == "waiting_period")
        assert "eligible" in failed_check.details.lower() or "2024-11-30" in failed_check.details


class TestTC006_DentalPartial:
    """TC006: Dental claim with covered + excluded procedures — PARTIAL."""

    def test_partial_dental_approval(self, policy):
        request = ClaimRequest(
            member_id="EMP002",
            claim_category=ClaimCategory.DENTAL,
            treatment_date="2024-10-15",
            claimed_amount=12000,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.HOSPITAL_BILL)],
        )
        extracted = ExtractedClaimData(
            documents=[
                ExtractedDocumentData(
                    document_type=DocumentType.HOSPITAL_BILL,
                    file_id="F1",
                    line_items=[
                        ExtractedLineItem(description="Root Canal Treatment", amount=8000),
                        ExtractedLineItem(description="Teeth Whitening", amount=4000),
                    ],
                    total_amount=12000,
                ),
            ],
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.PARTIAL
        assert result.approved_amount == 8000  # Only root canal approved
        # Verify line-item decisions
        assert len(result.line_item_decisions) == 2
        root_canal = next(l for l in result.line_item_decisions if "Root Canal" in l.description)
        whitening = next(l for l in result.line_item_decisions if "Whitening" in l.description)
        assert root_canal.approved is True
        assert whitening.approved is False


class TestTC007_PreAuthMissing:
    """TC007: MRI without pre-authorization — REJECTED."""

    def test_mri_pre_auth_required(self, policy):
        request = ClaimRequest(
            member_id="EMP007",
            claim_category=ClaimCategory.DIAGNOSTIC,
            treatment_date="2024-11-02",
            claimed_amount=15000,
            documents=[
                DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION),
                DocumentInput(file_id="F2", actual_type=DocumentType.LAB_REPORT),
                DocumentInput(file_id="F3", actual_type=DocumentType.HOSPITAL_BILL),
            ],
        )
        extracted = ExtractedClaimData(
            documents=[
                ExtractedDocumentData(
                    document_type=DocumentType.PRESCRIPTION,
                    file_id="F1",
                    tests_ordered=["MRI Lumbar Spine"],
                ),
                ExtractedDocumentData(
                    document_type=DocumentType.LAB_REPORT,
                    file_id="F2",
                    treatment="MRI Lumbar Spine",
                ),
                ExtractedDocumentData(
                    document_type=DocumentType.HOSPITAL_BILL,
                    file_id="F3",
                    line_items=[ExtractedLineItem(description="MRI Lumbar Spine", amount=15000)],
                    total_amount=15000,
                ),
            ],
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.REJECTED
        assert "PRE_AUTH_MISSING" in result.rejection_reasons


class TestTC008_PerClaimLimit:
    """TC008: Claimed amount exceeds per-claim limit of ₹5,000 — REJECTED."""

    def test_per_claim_limit_exceeded(self, policy):
        request = ClaimRequest(
            member_id="EMP003",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-10-20",
            claimed_amount=7500,
            ytd_claims_amount=10000,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)],
        )
        extracted = ExtractedClaimData(primary_diagnosis="Gastroenteritis")

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.REJECTED
        assert "PER_CLAIM_EXCEEDED" in result.rejection_reasons
        # Check that the message mentions both amounts
        failed_check = next(c for c in result.checks if c.check_name == "per_claim_limit")
        assert "7,500" in failed_check.details or "7500" in failed_check.details
        assert "5,000" in failed_check.details or "5000" in failed_check.details


class TestTC010_NetworkDiscount:
    """TC010: Network hospital discount applied before co-pay."""

    def test_network_discount_then_copay(self, policy):
        request = ClaimRequest(
            member_id="EMP010",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-03",
            claimed_amount=4500,
            hospital_name="Apollo Hospitals",
            ytd_claims_amount=8000,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)],
        )
        extracted = ExtractedClaimData(
            primary_diagnosis="Acute Bronchitis",
            hospital_name="Apollo Hospitals",
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.APPROVED
        # 4500 - 20% network discount = 3600, then 10% co-pay = 360, final = 3240
        assert result.approved_amount == 3240


class TestTC012_ExcludedTreatment:
    """TC012: Obesity/bariatric treatment — excluded condition — REJECTED."""

    def test_excluded_condition(self, policy):
        request = ClaimRequest(
            member_id="EMP009",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-10-18",
            claimed_amount=8000,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)],
        )
        extracted = ExtractedClaimData(
            primary_diagnosis="Morbid Obesity — BMI 37",
            documents=[
                ExtractedDocumentData(
                    document_type=DocumentType.PRESCRIPTION,
                    file_id="F1",
                    diagnosis="Morbid Obesity — BMI 37",
                    treatment="Bariatric Consultation and Customised Diet Plan",
                ),
            ],
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.REJECTED
        assert "EXCLUDED_CONDITION" in result.rejection_reasons


class TestTC011_PolicyStillWorks:
    """TC011: Even with partial data, policy engine should still approve valid claims."""

    def test_alternative_medicine_approval(self, policy):
        request = ClaimRequest(
            member_id="EMP006",
            claim_category=ClaimCategory.ALTERNATIVE_MEDICINE,
            treatment_date="2024-10-28",
            claimed_amount=4000,
            documents=[DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)],
        )
        extracted = ExtractedClaimData(
            primary_diagnosis="Chronic Joint Pain",
            documents=[
                ExtractedDocumentData(
                    document_type=DocumentType.PRESCRIPTION,
                    file_id="F1",
                    diagnosis="Chronic Joint Pain",
                    treatment="Panchakarma Therapy",
                ),
            ],
        )

        result = evaluate_claim(request, extracted, policy)

        assert result.decision == Decision.APPROVED
        assert result.approved_amount == 4000  # No co-pay for alternative medicine
