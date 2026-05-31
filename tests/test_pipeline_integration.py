"""Integration tests — run the full pipeline with test case data."""

import pytest
import asyncio
from app.models.claim import ClaimRequest, DocumentInput, DocumentType, DocumentQuality, ClaimCategory
from app.pipeline.graph import process_claim


class TestFullPipeline:
    """Integration tests using actual test case scenarios."""

    @pytest.mark.asyncio
    async def test_tc004_clean_approval(self):
        """TC004: Clean consultation should be approved at ₹1,350."""
        request = ClaimRequest(
            member_id="EMP001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-11-01",
            claimed_amount=1500,
            ytd_claims_amount=5000,
            documents=[
                DocumentInput(
                    file_id="F007",
                    actual_type=DocumentType.PRESCRIPTION,
                    patient_name_on_doc="Rajesh Kumar",
                    content={
                        "doctor_name": "Dr. Arun Sharma",
                        "doctor_registration": "KA/45678/2015",
                        "patient_name": "Rajesh Kumar",
                        "date": "2024-11-01",
                        "diagnosis": "Viral Fever",
                        "medicines": ["Paracetamol 650mg", "Vitamin C 500mg"],
                    },
                ),
                DocumentInput(
                    file_id="F008",
                    actual_type=DocumentType.HOSPITAL_BILL,
                    patient_name_on_doc="Rajesh Kumar",
                    content={
                        "hospital_name": "City Clinic, Bengaluru",
                        "patient_name": "Rajesh Kumar",
                        "date": "2024-11-01",
                        "line_items": [
                            {"description": "Consultation Fee", "amount": 1000},
                            {"description": "CBC Test", "amount": 300},
                            {"description": "Dengue NS1 Test", "amount": 200},
                        ],
                        "total": 1500,
                    },
                ),
            ],
        )

        decision = await process_claim(request)

        assert decision.decision.value == "APPROVED"
        assert decision.approved_amount == 1350
        assert decision.confidence_score > 0.85
        assert decision.trace is not None

    @pytest.mark.asyncio
    async def test_tc001_wrong_document(self):
        """TC001: Wrong document should halt with specific error."""
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

        decision = await process_claim(request)

        assert decision.decision is None
        assert decision.error_message is not None
        assert "Hospital Bill" in decision.error_message or "HOSPITAL_BILL" in decision.error_message

    @pytest.mark.asyncio
    async def test_tc011_graceful_degradation(self):
        """TC011: Component failure should not crash; produces decision with low confidence."""
        request = ClaimRequest(
            member_id="EMP006",
            claim_category=ClaimCategory.ALTERNATIVE_MEDICINE,
            treatment_date="2024-10-28",
            claimed_amount=4000,
            simulate_component_failure=True,
            documents=[
                DocumentInput(
                    file_id="F021",
                    actual_type=DocumentType.PRESCRIPTION,
                    patient_name_on_doc="Kavita Nair",
                    content={
                        "doctor_name": "Vaidya T. Krishnan",
                        "doctor_registration": "AYUR/KL/2345/2019",
                        "diagnosis": "Chronic Joint Pain",
                        "treatment": "Panchakarma Therapy",
                    },
                ),
                DocumentInput(
                    file_id="F022",
                    actual_type=DocumentType.HOSPITAL_BILL,
                    patient_name_on_doc="Kavita Nair",
                    content={
                        "hospital_name": "Ayur Wellness Centre",
                        "total": 4000,
                        "line_items": [
                            {"description": "Panchakarma Therapy (5 sessions)", "amount": 3000},
                            {"description": "Consultation", "amount": 1000},
                        ],
                    },
                ),
            ],
        )

        decision = await process_claim(request)

        # Should not crash
        assert decision is not None
        # Should produce a decision
        assert decision.decision is not None
        # Confidence should be lower than normal
        assert decision.confidence_score < 0.85
        # Should indicate component failure
        assert decision.manual_review_recommended is True

    @pytest.mark.asyncio
    async def test_tc009_fraud_manual_review(self):
        """TC009: Multiple same-day claims should route to MANUAL_REVIEW."""
        from app.models.claim import ClaimHistoryItem

        request = ClaimRequest(
            member_id="EMP008",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date="2024-10-30",
            claimed_amount=4800,
            claims_history=[
                ClaimHistoryItem(claim_id="CLM_0081", date="2024-10-30", amount=1200, provider="City Clinic A"),
                ClaimHistoryItem(claim_id="CLM_0082", date="2024-10-30", amount=1800, provider="City Clinic B"),
                ClaimHistoryItem(claim_id="CLM_0083", date="2024-10-30", amount=2100, provider="Wellness Center"),
            ],
            documents=[
                DocumentInput(
                    file_id="F017",
                    actual_type=DocumentType.PRESCRIPTION,
                    patient_name_on_doc="Ravi Menon",
                    content={"diagnosis": "Migraine", "doctor_name": "Dr. S. Khan"},
                ),
                DocumentInput(
                    file_id="F018",
                    actual_type=DocumentType.HOSPITAL_BILL,
                    patient_name_on_doc="Ravi Menon",
                    content={"total": 4800},
                ),
            ],
        )

        decision = await process_claim(request)

        assert decision.decision.value == "MANUAL_REVIEW"
        assert len(decision.fraud_signals) > 0
