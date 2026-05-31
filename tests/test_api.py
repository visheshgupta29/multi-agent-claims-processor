"""API endpoint tests — exercises FastAPI routes directly."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Health check endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "plum-claims-processor"


class TestClaimSubmission:
    """POST /api/claims/submit tests."""

    @pytest.mark.asyncio
    async def test_tc004_clean_approval(self, client):
        """TC004 data submitted via API should return APPROVED."""
        payload = {
            "member_id": "EMP001",
            "claim_category": "CONSULTATION",
            "treatment_date": "2024-11-01",
            "claimed_amount": 1500,
            "ytd_claims_amount": 5000,
            "documents": [
                {
                    "file_id": "F007",
                    "actual_type": "PRESCRIPTION",
                    "patient_name_on_doc": "Rajesh Kumar",
                    "content": {
                        "doctor_name": "Dr. Arun Sharma",
                        "doctor_registration": "KA/45678/2015",
                        "patient_name": "Rajesh Kumar",
                        "date": "2024-11-01",
                        "diagnosis": "Viral Fever",
                        "medicines": ["Paracetamol 650mg", "Vitamin C 500mg"],
                    },
                },
                {
                    "file_id": "F008",
                    "actual_type": "HOSPITAL_BILL",
                    "patient_name_on_doc": "Rajesh Kumar",
                    "content": {
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
                },
            ],
        }

        response = await client.post("/api/claims/submit", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["decision"] == "APPROVED"
        assert data["approved_amount"] == 1350
        assert data["confidence_score"] > 0.85
        assert data["trace"] is not None
        assert len(data["trace"]["steps"]) >= 5

    @pytest.mark.asyncio
    async def test_document_halt_returns_error(self, client):
        """Missing required document should halt with specific error."""
        payload = {
            "member_id": "EMP001",
            "claim_category": "CONSULTATION",
            "treatment_date": "2024-11-01",
            "claimed_amount": 1500,
            "documents": [
                {
                    "file_id": "F001",
                    "actual_type": "PRESCRIPTION",
                },
                {
                    "file_id": "F002",
                    "actual_type": "PRESCRIPTION",
                },
            ],
        }

        response = await client.post("/api/claims/submit", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["decision"] is None
        assert data["error_message"] is not None
        assert "HOSPITAL_BILL" in data["error_message"] or "Hospital Bill" in data["error_message"]

    @pytest.mark.asyncio
    async def test_invalid_payload_returns_422(self, client):
        """Malformed request should return 422 validation error."""
        payload = {
            "member_id": "EMP001",
            # Missing required fields: claim_category, treatment_date, claimed_amount, documents
        }

        response = await client.post("/api/claims/submit", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_member_returns_halt(self, client):
        """Non-existent member should halt at intake."""
        payload = {
            "member_id": "NONEXISTENT",
            "claim_category": "CONSULTATION",
            "treatment_date": "2024-11-01",
            "claimed_amount": 1500,
            "documents": [
                {"file_id": "F001", "actual_type": "PRESCRIPTION"},
                {"file_id": "F002", "actual_type": "HOSPITAL_BILL"},
            ],
        }

        response = await client.post("/api/claims/submit", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] is None
        assert "not found" in data["error_message"].lower()


class TestClaimRetrieval:
    """GET /api/claims/{claim_id} and /api/traces/{claim_id} tests."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_claim_returns_404(self, client):
        response = await client.get("/api/claims/CLM_NONEXISTENT")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_trace_returns_404(self, client):
        response = await client.get("/api/traces/CLM_NONEXISTENT")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_then_retrieve(self, client):
        """Submit a claim, then retrieve it by ID."""
        payload = {
            "member_id": "EMP001",
            "claim_category": "CONSULTATION",
            "treatment_date": "2024-11-01",
            "claimed_amount": 1500,
            "ytd_claims_amount": 5000,
            "documents": [
                {
                    "file_id": "F007",
                    "actual_type": "PRESCRIPTION",
                    "patient_name_on_doc": "Rajesh Kumar",
                    "content": {
                        "doctor_name": "Dr. Arun Sharma",
                        "patient_name": "Rajesh Kumar",
                        "diagnosis": "Viral Fever",
                    },
                },
                {
                    "file_id": "F008",
                    "actual_type": "HOSPITAL_BILL",
                    "patient_name_on_doc": "Rajesh Kumar",
                    "content": {
                        "hospital_name": "City Clinic",
                        "patient_name": "Rajesh Kumar",
                        "total": 1500,
                    },
                },
            ],
        }

        # Submit
        submit_resp = await client.post("/api/claims/submit", json=payload)
        assert submit_resp.status_code == 200
        claim_id = submit_resp.json()["claim_id"]

        # Retrieve claim
        get_resp = await client.get(f"/api/claims/{claim_id}")
        assert get_resp.status_code == 200

        # Retrieve trace
        trace_resp = await client.get(f"/api/traces/{claim_id}")
        assert trace_resp.status_code == 200
        trace_data = trace_resp.json()
        assert trace_data["claim_id"] == claim_id
        assert len(trace_data["steps"]) >= 4


class TestListClaims:
    """GET /api/claims tests."""

    @pytest.mark.asyncio
    async def test_list_claims(self, client):
        response = await client.get("/api/claims")
        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert "count" in data


class TestPolicySummary:
    """GET /api/policy/summary tests."""

    @pytest.mark.asyncio
    async def test_policy_summary(self, client):
        response = await client.get("/api/policy/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["policy_id"] == "PLUM_GHI_2024"
        assert "categories" in data
        assert "coverage" in data
        assert data["coverage"]["annual_opd_limit"] > 0
