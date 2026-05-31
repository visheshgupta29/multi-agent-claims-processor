"""Core claim data models — inputs, decisions, and trace structures."""

from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# --- Enums ---

class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class Decision(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    PHARMACY_BILL = "PHARMACY_BILL"
    LAB_REPORT = "LAB_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    DENTAL_REPORT = "DENTAL_REPORT"


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    UNREADABLE = "UNREADABLE"


class StepStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class TraceStatus(str, Enum):
    COMPLETED = "COMPLETED"
    HALTED_EARLY = "HALTED_EARLY"
    ERROR = "ERROR"


# --- Input Models ---

class DocumentInput(BaseModel):
    file_id: str
    file_name: str = ""
    actual_type: Optional[DocumentType] = None
    quality: Optional[DocumentQuality] = None
    patient_name_on_doc: Optional[str] = None
    content: Optional[dict] = None
    file_data: Optional[bytes] = Field(None, exclude=True)


class ClaimHistoryItem(BaseModel):
    claim_id: str
    date: str
    amount: float
    provider: str = ""


class ClaimRequest(BaseModel):
    member_id: str
    policy_id: str = "PLUM_GHI_2024"
    claim_category: ClaimCategory
    treatment_date: str
    claimed_amount: float
    hospital_name: Optional[str] = None
    ytd_claims_amount: float = 0.0
    documents: list[DocumentInput]
    claims_history: list[ClaimHistoryItem] = []
    simulate_component_failure: bool = False


# --- Extraction Models ---

class ExtractedLineItem(BaseModel):
    description: str
    amount: float


class ExtractedDocumentData(BaseModel):
    document_type: DocumentType
    file_id: str
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_registration: Optional[str] = None
    hospital_name: Optional[str] = None
    date: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    medicines: list[str] = []
    tests_ordered: list[str] = []
    line_items: list[ExtractedLineItem] = []
    total_amount: Optional[float] = None
    confidence: float = 1.0
    extraction_notes: list[str] = []


class ExtractedClaimData(BaseModel):
    documents: list[ExtractedDocumentData] = []
    primary_diagnosis: Optional[str] = None
    primary_patient_name: Optional[str] = None
    primary_doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    total_billed_amount: Optional[float] = None
    overall_confidence: float = 1.0


# --- Decision Models ---

class LineItemDecision(BaseModel):
    description: str
    amount: float
    approved: bool
    reason: str = ""


class PolicyCheckResult(BaseModel):
    check_name: str
    passed: bool
    details: str
    policy_rule: str = ""


class FraudSignal(BaseModel):
    signal_name: str
    severity: str  # LOW, MEDIUM, HIGH
    details: str


class ClaimDecision(BaseModel):
    claim_id: str
    decision: Optional[Decision] = None
    approved_amount: Optional[float] = None
    rejection_reasons: list[str] = []
    confidence_score: float = 0.0
    explanation: str = ""
    line_item_decisions: list[LineItemDecision] = []
    policy_checks: list[PolicyCheckResult] = []
    fraud_signals: list[FraudSignal] = []
    manual_review_recommended: bool = False
    error_message: Optional[str] = None
    trace: Optional["ClaimTrace"] = None


# --- Trace Models ---

class Check(BaseModel):
    check_name: str
    result: str  # PASS or FAIL
    details: str
    relevant_policy_rule: str = ""


class TraceStep(BaseModel):
    step_name: str
    status: StepStatus
    started_at: Optional[datetime] = None
    duration_ms: int = 0
    input_summary: dict = {}
    output_summary: dict = {}
    checks_performed: list[Check] = []
    confidence_impact: float = 0.0
    error_details: Optional[str] = None
    notes: list[str] = []


class ClaimTrace(BaseModel):
    claim_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    member_id: str
    claim_category: str = ""
    status: TraceStatus = TraceStatus.COMPLETED
    steps: list[TraceStep] = []
    final_decision: Optional[Decision] = None
    approved_amount: Optional[float] = None
    confidence_score: float = 1.0
    total_duration_ms: int = 0
    error_message: Optional[str] = None


# Rebuild for forward reference
ClaimDecision.model_rebuild()
