"""FastAPI application — claim submission and trace query endpoints."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models.claim import ClaimRequest, ClaimDecision
from app.pipeline.graph import process_claim
from app.services.trace_store import trace_store

# When behind HTTPS reverse proxy (Render, Railway), explicitly declare server URL
# so Swagger UI uses https:// scheme for requests.
_render_url = os.environ.get("RENDER_EXTERNAL_URL")  # Render sets this automatically
_servers = [{"url": _render_url, "description": "Production"}] if _render_url else None

app = FastAPI(
    title="Plum Claims Processing System",
    description="AI-powered health insurance claims processing with multi-agent pipeline",
    version="1.0.0",
    servers=_servers,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with system info and links."""
    return {
        "system": "Plum Health Insurance Claims Processing System",
        "description": "Multi-agent AI system for automated OPD claims adjudication",
        "version": "1.0.0",
        "agents": [
            "Intake Validation",
            "Document Verification (GATE)",
            "Data Extraction (Gemini Vision)",
            "Policy Engine (Deterministic)",
            "Fraud Detection",
            "Decision Aggregator",
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "submit_claim": "POST /api/claims/submit",
            "get_claim": "GET /api/claims/{claim_id}",
            "get_trace": "GET /api/traces/{claim_id}",
            "list_claims": "GET /api/claims",
            "policy_summary": "GET /api/policy/summary",
        },
        "test_results": "27/27 tests passing, 12/12 eval cases passing",
        "repo": "https://github.com/visheshgupta29/multi-agent-claims-processor",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "plum-claims-processor"}


@app.post("/api/claims/submit", response_model=ClaimDecision)
async def submit_claim(request: ClaimRequest):
    """Submit a claim for processing through the multi-agent pipeline.

    The system will:
    1. Validate member eligibility
    2. Verify documents (may halt early with specific error)
    3. Extract structured data from documents
    4. Apply policy rules deterministically
    5. Check for fraud signals
    6. Produce a final decision with full trace
    """
    try:
        decision = await process_claim(request)

        # Persist the decision and trace
        trace_store.save_decision(
            decision,
            request_data={"claimed_amount": request.claimed_amount}
        )

        return decision

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal processing error: {str(e)}")


@app.get("/api/claims/{claim_id}")
async def get_claim(claim_id: str):
    """Retrieve a processed claim decision by ID."""
    result = trace_store.get_decision(claim_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return result.get("decision_obj", result)


@app.get("/api/traces/{claim_id}")
async def get_trace(claim_id: str):
    """Retrieve the full processing trace for a claim.

    Shows every step, check, confidence impact, and decision reasoning.
    """
    trace = trace_store.get_trace(claim_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found for claim {claim_id}")
    return trace


@app.get("/api/claims")
async def list_claims(member_id: str = None, limit: int = 50):
    """List recent claims, optionally filtered by member ID."""
    claims = trace_store.list_claims(member_id=member_id, limit=limit)
    return {"claims": claims, "count": len(claims)}


@app.get("/api/policy/summary")
async def get_policy_summary():
    """Get a summary of the active policy terms."""
    from app.policy.loader import load_policy
    policy = load_policy()
    return {
        "policy_id": policy.policy_id,
        "policy_name": policy.policy_name,
        "insurer": policy.insurer,
        "coverage": {
            "sum_insured": policy.coverage.sum_insured_per_employee,
            "annual_opd_limit": policy.coverage.annual_opd_limit,
            "per_claim_limit": policy.coverage.per_claim_limit,
        },
        "categories": list(policy.opd_categories.keys()),
        "network_hospitals": policy.network_hospitals,
        "member_count": len(policy.members),
    }
