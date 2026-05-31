"""Tests for the document verification agent."""

import pytest
from app.models.claim import (
    ClaimRequest,
    DocumentInput,
    DocumentType,
    DocumentQuality,
    ClaimCategory,
)
from app.agents.document_verification import verify_documents


class TestTC001_WrongDocument:
    """TC001: Wrong document uploaded — should halt with specific message."""

    def test_missing_hospital_bill(self, policy):
        request = ClaimRequest(
            member_id="EMP001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-01",
            claimed_amount=1500,
            documents=[
                DocumentInput(file_id="F001", file_name="dr_sharma_prescription.jpg",
                             actual_type=DocumentType.PRESCRIPTION),
                DocumentInput(file_id="F002", file_name="another_prescription.jpg",
                             actual_type=DocumentType.PRESCRIPTION),
            ],
        )

        result = verify_documents(request, policy)

        assert not result.passed
        assert result.halt is True
        assert result.error_message is not None
        # Must mention what was uploaded and what's needed
        assert "Prescription" in result.error_message or "PRESCRIPTION" in result.error_message
        assert "Hospital Bill" in result.error_message or "HOSPITAL_BILL" in result.error_message


class TestTC002_UnreadableDocument:
    """TC002: Unreadable pharmacy bill — should halt with re-upload request."""

    def test_unreadable_document(self, policy):
        request = ClaimRequest(
            member_id="EMP004",
            claim_category=ClaimCategory.PHARMACY,
            treatment_date="2024-10-25",
            claimed_amount=800,
            documents=[
                DocumentInput(file_id="F003", file_name="prescription.jpg",
                             actual_type=DocumentType.PRESCRIPTION, quality=DocumentQuality.GOOD),
                DocumentInput(file_id="F004", file_name="blurry_bill.jpg",
                             actual_type=DocumentType.PHARMACY_BILL, quality=DocumentQuality.UNREADABLE),
            ],
        )

        result = verify_documents(request, policy)

        assert not result.passed
        assert result.halt is True
        assert "re-upload" in result.error_message.lower() or "unreadable" in result.error_message.lower()


class TestTC003_DifferentPatients:
    """TC003: Documents belong to different patients — should halt."""

    def test_patient_name_mismatch(self, policy):
        request = ClaimRequest(
            member_id="EMP001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-01",
            claimed_amount=1500,
            documents=[
                DocumentInput(file_id="F005", file_name="prescription_rajesh.jpg",
                             actual_type=DocumentType.PRESCRIPTION,
                             patient_name_on_doc="Rajesh Kumar"),
                DocumentInput(file_id="F006", file_name="bill_arjun.jpg",
                             actual_type=DocumentType.HOSPITAL_BILL,
                             patient_name_on_doc="Arjun Mehta"),
            ],
        )

        result = verify_documents(request, policy)

        assert not result.passed
        assert result.halt is True
        assert "Rajesh Kumar" in result.error_message
        assert "Arjun Mehta" in result.error_message


class TestValidDocuments:
    """Test that valid documents pass verification."""

    def test_complete_consultation_docs(self, policy):
        request = ClaimRequest(
            member_id="EMP001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-01",
            claimed_amount=1500,
            documents=[
                DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION,
                             patient_name_on_doc="Rajesh Kumar"),
                DocumentInput(file_id="F2", actual_type=DocumentType.HOSPITAL_BILL,
                             patient_name_on_doc="Rajesh Kumar"),
            ],
        )

        result = verify_documents(request, policy)

        assert result.passed
        assert not result.halt
