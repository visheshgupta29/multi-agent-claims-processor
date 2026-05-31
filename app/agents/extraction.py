"""Extraction Agent — uses Gemini Vision to extract structured data from documents.

When documents have pre-parsed content (from test cases), uses that directly.
When documents have image/PDF data, uses Gemini Vision for OCR and extraction.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.models.claim import (
    ClaimRequest,
    DocumentInput,
    ExtractedClaimData,
    ExtractedDocumentData,
    ExtractedLineItem,
    DocumentType,
)
from app.services.gemini import gemini_client, GeminiError


EXTRACTION_PROMPT = """You are a medical document data extraction system for an Indian health insurance company.
Extract structured information from this document. Return a JSON object with these fields:

{
  "patient_name": "string or null",
  "doctor_name": "string or null",
  "doctor_registration": "string or null",
  "hospital_name": "string or null",
  "date": "string (YYYY-MM-DD) or null",
  "diagnosis": "string or null",
  "treatment": "string or null",
  "medicines": ["list of medicine names"],
  "tests_ordered": ["list of tests"],
  "line_items": [{"description": "string", "amount": number}],
  "total_amount": number or null,
  "confidence": 0.0 to 1.0
}

Rules:
- Extract only what is clearly visible. Do not guess or hallucinate.
- For amounts, extract the numeric value in INR.
- If a field is not present or unreadable, set it to null.
- Set confidence based on document quality (1.0 = perfect, 0.5 = partially readable, < 0.3 = mostly unreadable).
- For Indian medical documents, recognize formats like "1-1-1 x 5 days" as dosage instructions.
- Registration numbers follow state patterns like KA/12345/2020.
"""


async def extract_from_documents(
    request: ClaimRequest,
    simulate_failure: bool = False,
) -> ExtractedClaimData:
    """Extract structured data from all claim documents.

    If documents have pre-parsed content (test mode), uses that directly.
    If documents have image data, uses Gemini Vision.
    """
    extracted_docs: list[ExtractedDocumentData] = []
    overall_confidence = 1.0

    for doc in request.documents:
        if simulate_failure and doc == request.documents[-1]:
            # Simulate component failure for TC011
            raise ExtractionComponentError("Simulated extraction failure for testing graceful degradation.")

        extracted = await _extract_single_document(doc)
        extracted_docs.append(extracted)
        overall_confidence = min(overall_confidence, extracted.confidence)

    # Build aggregate extracted data
    result = ExtractedClaimData(
        documents=extracted_docs,
        overall_confidence=overall_confidence,
    )

    # Derive primary fields from extracted docs
    _populate_primary_fields(result, request)

    return result


async def _extract_single_document(doc: DocumentInput) -> ExtractedDocumentData:
    """Extract data from a single document."""
    # If pre-parsed content is available (test mode), use it directly
    if doc.content:
        return _extract_from_content(doc)

    # If image data is available, use Gemini Vision
    if doc.file_data:
        return await _extract_with_gemini(doc)

    # No content or image — return minimal extraction
    return ExtractedDocumentData(
        document_type=doc.actual_type or DocumentType.PRESCRIPTION,
        file_id=doc.file_id,
        confidence=0.5,
        extraction_notes=["No document content or image data available."],
    )


def _extract_from_content(doc: DocumentInput) -> ExtractedDocumentData:
    """Extract from pre-parsed content dict (used in test mode)."""
    content = doc.content or {}

    line_items = []
    if "line_items" in content:
        for item in content["line_items"]:
            line_items.append(ExtractedLineItem(
                description=item.get("description", ""),
                amount=item.get("amount", 0),
            ))

    return ExtractedDocumentData(
        document_type=doc.actual_type or DocumentType.PRESCRIPTION,
        file_id=doc.file_id,
        patient_name=content.get("patient_name"),
        doctor_name=content.get("doctor_name"),
        doctor_registration=content.get("doctor_registration"),
        hospital_name=content.get("hospital_name"),
        date=content.get("date"),
        diagnosis=content.get("diagnosis"),
        treatment=content.get("treatment"),
        medicines=content.get("medicines", []),
        tests_ordered=content.get("tests_ordered", []),
        line_items=line_items,
        total_amount=content.get("total"),
        confidence=0.95,  # Pre-parsed content is high confidence
        extraction_notes=["Extracted from structured content (test mode)."],
    )


async def _extract_with_gemini(doc: DocumentInput) -> ExtractedDocumentData:
    """Use Gemini Vision to extract data from document image."""
    try:
        result = await gemini_client.generate_structured(
            prompt=EXTRACTION_PROMPT,
            image_data=doc.file_data,
        )

        line_items = []
        for item in result.get("line_items", []):
            line_items.append(ExtractedLineItem(
                description=item.get("description", ""),
                amount=float(item.get("amount", 0)),
            ))

        return ExtractedDocumentData(
            document_type=doc.actual_type or DocumentType.PRESCRIPTION,
            file_id=doc.file_id,
            patient_name=result.get("patient_name"),
            doctor_name=result.get("doctor_name"),
            doctor_registration=result.get("doctor_registration"),
            hospital_name=result.get("hospital_name"),
            date=result.get("date"),
            diagnosis=result.get("diagnosis"),
            treatment=result.get("treatment"),
            medicines=result.get("medicines", []),
            tests_ordered=result.get("tests_ordered", []),
            line_items=line_items,
            total_amount=result.get("total_amount"),
            confidence=float(result.get("confidence", 0.7)),
            extraction_notes=["Extracted via Gemini Vision."],
        )

    except GeminiError as e:
        return ExtractedDocumentData(
            document_type=doc.actual_type or DocumentType.PRESCRIPTION,
            file_id=doc.file_id,
            confidence=0.3,
            extraction_notes=[f"Gemini extraction failed: {str(e)}. Using partial data."],
        )


def _populate_primary_fields(result: ExtractedClaimData, request: ClaimRequest):
    """Derive primary/aggregate fields from individual document extractions."""
    for doc in result.documents:
        if doc.diagnosis and not result.primary_diagnosis:
            result.primary_diagnosis = doc.diagnosis
        if doc.patient_name and not result.primary_patient_name:
            result.primary_patient_name = doc.patient_name
        if doc.doctor_name and not result.primary_doctor_name:
            result.primary_doctor_name = doc.doctor_name
        if doc.hospital_name and not result.hospital_name:
            result.hospital_name = doc.hospital_name
        if doc.total_amount and not result.total_billed_amount:
            result.total_billed_amount = doc.total_amount

    # Use request's hospital_name if not found in docs
    if not result.hospital_name and request.hospital_name:
        result.hospital_name = request.hospital_name


class ExtractionComponentError(Exception):
    """Raised when extraction component fails (for graceful degradation testing)."""
    pass
