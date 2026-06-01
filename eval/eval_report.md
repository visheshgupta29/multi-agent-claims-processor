# Evaluation Report

Generated: 2026-06-01T18:48:37.655619

## Summary

**12/12 test cases passed**

| Case | Name | Expected | Actual | Amount (Expected/Actual) | Status |
|------|------|----------|--------|--------------------------|--------|
| TC001 | Wrong Document Uploaded | HALT | HALT | — / — | ✅ PASS |
| TC002 | Unreadable Document | HALT | HALT | — / — | ✅ PASS |
| TC003 | Documents Belong to Different Patients | HALT | HALT | — / — | ✅ PASS |
| TC004 | Clean Consultation — Full Approval | APPROVED | APPROVED | ₹1,350 / ₹1,350 | ✅ PASS |
| TC005 | Waiting Period — Diabetes | REJECTED | REJECTED | — / — | ✅ PASS |
| TC006 | Dental Partial Approval — Cosmetic Exclusion | PARTIAL | PARTIAL | ₹8,000 / ₹8,000 | ✅ PASS |
| TC007 | MRI Without Pre-Authorization | REJECTED | REJECTED | — / — | ✅ PASS |
| TC008 | Per-Claim Limit Exceeded | REJECTED | REJECTED | — / — | ✅ PASS |
| TC009 | Fraud Signal — Multiple Same-Day Claims | MANUAL_REVIEW | MANUAL_REVIEW | — / ₹4,320 | ✅ PASS |
| TC010 | Network Hospital — Discount Applied | APPROVED | APPROVED | ₹3,240 / ₹3,240 | ✅ PASS |
| TC011 | Component Failure — Graceful Degradation | APPROVED | APPROVED | — / ₹4,000 | ✅ PASS |
| TC012 | Excluded Treatment | REJECTED | REJECTED | — / — | ✅ PASS |

---

## Detailed Results

### TC001: Wrong Document Uploaded

**Status:** ✅ PASS

**Decision:** HALT (no decision)

**Confidence:** 0.0

**Error Message:**
> Your consultation claim is missing required documents. You uploaded: Prescription. Missing: Hospital Bill. Please upload the following document(s) to proceed: Hospital Bill.

**Explanation:**
```
Claim processing halted: Your consultation claim is missing required documents. You uploaded: Prescription. Missing: Hospital Bill. Please upload the following document(s) to proceed: Hospital Bill.
```

**Notes:**
- [REQUIREMENT] Stop before making any claim decision
- [REQUIREMENT] Tell the member specifically what document type was uploaded and what is needed instead
- [REQUIREMENT] Not return a generic error — the message must name the uploaded document type and the required document type

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Rajesh Kumar' (EMP001) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹1,500.
  - ✗ document_verification (FAILED) — 0ms
    - ✗ document_completeness: Your consultation claim is missing required documents. You uploaded: Prescription. Missing: Hospital

---

### TC002: Unreadable Document

**Status:** ✅ PASS

**Decision:** HALT (no decision)

**Confidence:** 0.0

**Error Message:**
> The following document(s) cannot be read: Pharmacy Bill (blurry_bill.jpg). The image appears to be blurry or unreadable. Please re-upload a clear photo or scan of the document(s).

**Explanation:**
```
Claim processing halted: The following document(s) cannot be read: Pharmacy Bill (blurry_bill.jpg). The image appears to be blurry or unreadable. Please re-upload a clear photo or scan of the document(s).
```

**Notes:**
- [REQUIREMENT] Identify that the pharmacy bill cannot be read
- [REQUIREMENT] Ask the member to re-upload that specific document
- [REQUIREMENT] Not reject the claim outright

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Sneha Reddy' (EMP004) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹800.
  - ✗ document_verification (FAILED) — 0ms
    - ✓ document_completeness: All required documents present: ['PHARMACY_BILL', 'PRESCRIPTION'].
    - ✗ document_quality: The following document(s) cannot be read: Pharmacy Bill (blurry_bill.jpg). The image appears to be b

---

### TC003: Documents Belong to Different Patients

**Status:** ✅ PASS

**Decision:** HALT (no decision)

**Confidence:** 0.0

**Error Message:**
> The uploaded documents appear to belong to different patients. Names found — Prescription: 'Rajesh Kumar'; Hospital Bill: 'Arjun Mehta'. All documents for a claim must belong to the same patient. Please verify and re-upload the correct documents.

**Explanation:**
```
Claim processing halted: The uploaded documents appear to belong to different patients. Names found — Prescription: 'Rajesh Kumar'; Hospital Bill: 'Arjun Mehta'. All documents for a claim must belong to the same patient. Please verify and re-upload the correct documents.
```

**Notes:**
- [REQUIREMENT] Detect that the documents belong to different people
- [REQUIREMENT] Surface this to the member with the specific names found on each document
- [REQUIREMENT] Not proceed to a claim decision

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Rajesh Kumar' (EMP001) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹1,500.
  - ✗ document_verification (FAILED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✗ patient_name_consistency: The uploaded documents appear to belong to different patients. Names found — Prescription: 'Rajesh K

---

### TC004: Clean Consultation — Full Approval

**Status:** ✅ PASS

**Decision:** APPROVED

**Approved Amount:** ₹1,350

**Confidence:** 0.95

**Explanation:**
```
Claim APPROVED for ₹1,350.
```

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Rajesh Kumar' (EMP001) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹1,500.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: All documents reference the same patient: 'Rajesh Kumar'.
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✓ extraction_validation (PASSED) — 3ms
    - ✓ extracted_patient_name_consistency: All 2 document(s) reference the same patient: 'Rajesh Kumar'.
    - ✓ document_date_proximity: All dated documents fall within 0 day(s) of each other.
    - ✓ category_required_fields: All required fields for CONSULTATION present in extracted data.
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'CONSULTATION' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-11-01.
    - ✓ minimum_claim_amount: Claimed ₹1500.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 214 days ago.
    - ✓ pre_authorization: No pre-authorization required for this claim.
    - ✓ per_claim_limit: Approvable amount ₹1,500 is within per-claim limit of ₹5,000.
    - ✓ sub_limit: Amount ₹1,350 is within category sub-limit of ₹2,000.
    - ✓ annual_opd_limit: YTD claims: ₹5,000. This claim: ₹1,350. Annual limit: ₹50,000. Remaining: ₹45,000.
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹1,500 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC005: Waiting Period — Diabetes

**Status:** ✅ PASS

**Decision:** REJECTED

**Confidence:** 0.95

**Explanation:**
```
Claim REJECTED. Reason(s): WAITING_PERIOD.
  - Member joined on 2024-09-01. Treatment on 2024-10-15 is within the 90-day waiting period for 'diabetes'. Member will be eligible for diabetes-related claims from 2024-11-30.
```

**Notes:**
- [REQUIREMENT] State the date from which the member will be eligible for diabetes-related claims

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Vikram Joshi' (EMP005) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹3,000.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: All documents reference the same patient: 'Vikram Joshi'.
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✓ extraction_validation (PASSED) — 0ms
    - ✓ extracted_patient_name_consistency: All 2 document(s) reference the same patient: 'Vikram Joshi'.
    - ✓ document_date_proximity: Only 1 of 2 document(s) had an extractable date — proximity check skipped.
    - ✓ category_required_fields: All required fields for CONSULTATION present in extracted data.
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'CONSULTATION' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-10-15.
    - ✓ minimum_claim_amount: Claimed ₹3000.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✗ waiting_period: Member joined on 2024-09-01. Treatment on 2024-10-15 is within the 90-day waiting period for 'diabet
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹3,000 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC006: Dental Partial Approval — Cosmetic Exclusion

**Status:** ✅ PASS

**Decision:** PARTIAL

**Approved Amount:** ₹8,000

**Confidence:** 0.95

**Explanation:**
```
Claim PARTIALLY APPROVED for ₹8,000.
Some line items were excluded:
  - Root Canal Treatment (₹8,000): ✓ Approved — Covered procedure.
  - Teeth Whitening (₹4,000): ✗ Rejected — 'Teeth Whitening' is an excluded cosmetic/dental procedure.
```

**Notes:**
- [REQUIREMENT] Itemize which line items were approved and which were rejected
- [REQUIREMENT] State the reason for each rejection at the line-item level

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Priya Singh' (EMP002) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 1 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹12,000.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: Insufficient documents with patient names to cross-validate (or names match).
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✗ extraction_validation (FAILED) — 0ms
    - ✓ extracted_patient_name_consistency: Only 1 of 1 document(s) had an extracted patient name — cross-validation skipped.
    - ✓ document_date_proximity: Only 0 of 1 document(s) had an extractable date — proximity check skipped.
    - ✗ category_required_fields: DENTAL claim is missing required extracted field(s): primary_diagnosis. Cannot auto-decide; routing 
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'DENTAL' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-10-15.
    - ✓ minimum_claim_amount: Claimed ₹12000.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 197 days ago.
    - ✓ pre_authorization: No pre-authorization required for this claim.
    - ✓ per_claim_limit: Approvable amount ₹8,000 is within per-claim limit of ₹10,000.
    - ✓ sub_limit: Amount ₹8,000 is within category sub-limit of ₹10,000.
    - ✓ annual_opd_limit: YTD claims: ₹0. This claim: ₹8,000. Annual limit: ₹50,000. Remaining: ₹50,000.
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹12,000 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC007: MRI Without Pre-Authorization

**Status:** ✅ PASS

**Decision:** REJECTED

**Confidence:** 0.95

**Explanation:**
```
Claim REJECTED. Reason(s): PRE_AUTH_MISSING.
  - Pre-authorization is required for MRI when amount exceeds ₹10,000. Claimed amount: ₹15,000. Please obtain pre-authorization and resubmit the claim.
```

**Notes:**
- [REQUIREMENT] Explain that pre-authorization was required and not obtained
- [REQUIREMENT] Tell the member what they should do to resubmit with pre-auth

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Suresh Patil' (EMP007) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 3 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹15,000.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['LAB_REPORT', 'HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: Insufficient documents with patient names to cross-validate (or names match).
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✗ extraction_validation (FAILED) — 0ms
    - ✓ extracted_patient_name_consistency: Only 0 of 3 document(s) had an extracted patient name — cross-validation skipped.
    - ✓ document_date_proximity: Only 0 of 3 document(s) had an extractable date — proximity check skipped.
    - ✗ category_required_fields: DIAGNOSTIC claim is missing required extracted field(s): primary_patient_name. Cannot auto-decide; r
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'DIAGNOSTIC' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-11-02.
    - ✓ minimum_claim_amount: Claimed ₹15000.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 215 days ago.
    - ✗ pre_authorization: Pre-authorization is required for MRI when amount exceeds ₹10,000. Claimed amount: ₹15,000. Please o
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹15,000 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC008: Per-Claim Limit Exceeded

**Status:** ✅ PASS

**Decision:** REJECTED

**Confidence:** 0.95

**Explanation:**
```
Claim REJECTED. Reason(s): PER_CLAIM_EXCEEDED.
  - Claimed amount ₹7,500 (approvable: ₹7,500) exceeds the per-claim limit of ₹5,000. Maximum allowed per claim is ₹5,000.
```

**Notes:**
- [REQUIREMENT] State the per-claim limit and the claimed amount clearly in the rejection message

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Amit Verma' (EMP003) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹7,500.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: Insufficient documents with patient names to cross-validate (or names match).
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✗ extraction_validation (FAILED) — 0ms
    - ✓ extracted_patient_name_consistency: Only 0 of 2 document(s) had an extracted patient name — cross-validation skipped.
    - ✓ document_date_proximity: Only 0 of 2 document(s) had an extractable date — proximity check skipped.
    - ✗ category_required_fields: CONSULTATION claim is missing required extracted field(s): primary_patient_name. Cannot auto-decide;
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'CONSULTATION' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-10-20.
    - ✓ minimum_claim_amount: Claimed ₹7500.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 202 days ago.
    - ✓ pre_authorization: No pre-authorization required for this claim.
    - ✗ per_claim_limit: Claimed amount ₹7,500 (approvable: ₹7,500) exceeds the per-claim limit of ₹5,000. Maximum allowed pe
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹7,500 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC009: Fraud Signal — Multiple Same-Day Claims

**Status:** ✅ PASS

**Decision:** MANUAL_REVIEW

**Approved Amount:** ₹4,320

**Confidence:** 0.6

**Explanation:**
```
Claim routed to MANUAL REVIEW.
  - [HIGH] SAME_DAY_CLAIMS_EXCEEDED: Member has 3 existing claim(s) on 2024-10-30 (limit: 2). This would be claim #4 on the same day. Previous claims from: City Clinic A, City Clinic B, Wellness Center. Total same-day amount: ₹9,900.
```

**Notes:**
- [REQUIREMENT] Flag the unusual same-day claim pattern
- [REQUIREMENT] Route to manual review rather than auto-rejecting
- [REQUIREMENT] Include the specific signals that triggered the flag in the output

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Ravi Menon' (EMP008) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹4,800.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: Insufficient documents with patient names to cross-validate (or names match).
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✗ extraction_validation (FAILED) — 0ms
    - ✓ extracted_patient_name_consistency: Only 0 of 2 document(s) had an extracted patient name — cross-validation skipped.
    - ✓ document_date_proximity: Only 0 of 2 document(s) had an extractable date — proximity check skipped.
    - ✗ category_required_fields: CONSULTATION claim is missing required extracted field(s): primary_patient_name. Cannot auto-decide;
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'CONSULTATION' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-10-30.
    - ✓ minimum_claim_amount: Claimed ₹4800.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 212 days ago.
    - ✓ pre_authorization: No pre-authorization required for this claim.
    - ✓ per_claim_limit: Approvable amount ₹4,800 is within per-claim limit of ₹5,000.
    - ✗ sub_limit: Amount ₹4,320 exceeds category sub-limit of ₹2,000. Capped at ₹2,000.
    - ✓ annual_opd_limit: YTD claims: ₹0. This claim: ₹4,320. Annual limit: ₹50,000. Remaining: ₹50,000.
  - ✓ fraud_detection (PASSED) — 0ms
    - ✗ same_day_claims: Member has 3 existing claim(s) on 2024-10-30 (limit: 2). This would be claim #4 on the same day. Pre
    - ✓ high_value_claim: Claimed amount ₹4,800 below threshold ₹25,000.
    - ✓ monthly_claims: Monthly claims count (3) within limit (6).

---

### TC010: Network Hospital — Discount Applied

**Status:** ✅ PASS

**Decision:** APPROVED

**Approved Amount:** ₹3,240

**Confidence:** 0.95

**Explanation:**
```
Claim APPROVED for ₹3,240.
```

**Notes:**
- [REQUIREMENT] Apply network discount before co-pay, not after
- [REQUIREMENT] Show the breakdown of discount and co-pay in the decision output

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Deepak Shah' (EMP010) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹4,500.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: All documents reference the same patient: 'Deepak Shah'.
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✓ extraction_validation (PASSED) — 0ms
    - ✓ extracted_patient_name_consistency: All 2 document(s) reference the same patient: 'Deepak Shah'.
    - ✓ document_date_proximity: Only 0 of 2 document(s) had an extractable date — proximity check skipped.
    - ✓ category_required_fields: All required fields for CONSULTATION present in extracted data.
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'CONSULTATION' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-11-03.
    - ✓ minimum_claim_amount: Claimed ₹4500.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 216 days ago.
    - ✓ pre_authorization: No pre-authorization required for this claim.
    - ✓ per_claim_limit: Approvable amount ₹4,500 is within per-claim limit of ₹5,000.
    - ✗ sub_limit: Amount ₹3,240 exceeds category sub-limit of ₹2,000. Capped at ₹2,000.
    - ✓ annual_opd_limit: YTD claims: ₹8,000. This claim: ₹3,240. Annual limit: ₹50,000. Remaining: ₹42,000.
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹4,500 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC011: Component Failure — Graceful Degradation

**Status:** ✅ PASS

**Decision:** APPROVED

**Approved Amount:** ₹4,000

**Confidence:** 0.4

**Explanation:**
```
Claim APPROVED for ₹4,000.

⚠ Component failures during processing:
  - Data extraction component failed: Simulated extraction failure for testing graceful degradation.
Manual review is recommended due to incomplete processing.
```

**Notes:**
- [REQUIREMENT] Not crash or return a 500 error
- [REQUIREMENT] Indicate in the output that a component failed and was skipped
- [REQUIREMENT] Return a confidence score lower than a normal full-pipeline approval
- [REQUIREMENT] Include a note that manual review is recommended due to incomplete processing

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Kavita Nair' (EMP006) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹4,000.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: Insufficient documents with patient names to cross-validate (or names match).
  - ⚠ data_extraction (ERROR) — 0ms
  - ✗ extraction_validation (FAILED) — 0ms
    - ✓ extracted_patient_name_consistency: Only 0 of 2 document(s) had an extracted patient name — cross-validation skipped.
    - ✓ document_date_proximity: Only 0 of 2 document(s) had an extractable date — proximity check skipped.
    - ✗ category_required_fields: ALTERNATIVE_MEDICINE claim is missing required extracted field(s): primary_patient_name. Cannot auto
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'ALTERNATIVE_MEDICINE' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-10-28.
    - ✓ minimum_claim_amount: Claimed ₹4000.0. Minimum: ₹500.0.
    - ✓ exclusion_check: No exclusions matched.
    - ✓ waiting_period: No applicable waiting period. Member joined 2024-04-01, 210 days ago.
    - ✓ pre_authorization: No pre-authorization required for this claim.
    - ✓ per_claim_limit: Approvable amount ₹4,000 is within per-claim limit of ₹8,000.
    - ✓ sub_limit: Amount ₹4,000 is within category sub-limit of ₹8,000.
    - ✓ annual_opd_limit: YTD claims: ₹0. This claim: ₹4,000. Annual limit: ₹50,000. Remaining: ₹50,000.
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹4,000 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---

### TC012: Excluded Treatment

**Status:** ✅ PASS

**Decision:** REJECTED

**Confidence:** 0.95

**Explanation:**
```
Claim REJECTED. Reason(s): EXCLUDED_CONDITION.
  - Treatment/diagnosis matches exclusion: 'Obesity and weight loss programs'. This is not covered under the policy.
```

**Trace Steps:**
  - ✓ intake_validation (PASSED) — 0ms
    - ✓ policy_id_validation: Policy ID valid.
    - ✓ member_eligibility: Member 'Anita Desai' (EMP009) found. Relationship: SELF.
    - ✓ policy_active: Policy status: ACTIVE. Period: 2024-04-01 to 2025-03-31.
    - ✓ documents_present: 2 document(s) attached.
    - ✓ amount_positive: Claimed amount: ₹8,000.
  - ✓ document_verification (PASSED) — 0ms
    - ✓ document_completeness: All required documents present: ['HOSPITAL_BILL', 'PRESCRIPTION'].
    - ✓ document_quality: All documents are readable.
    - ✓ patient_name_consistency: Insufficient documents with patient names to cross-validate (or names match).
  - ✓ data_extraction (PASSED) — 0ms
    - ✓ extraction_confidence: Overall extraction confidence: 0.95
  - ✗ extraction_validation (FAILED) — 0ms
    - ✓ extracted_patient_name_consistency: Only 0 of 2 document(s) had an extracted patient name — cross-validation skipped.
    - ✓ document_date_proximity: Only 0 of 2 document(s) had an extractable date — proximity check skipped.
    - ✗ category_required_fields: CONSULTATION claim is missing required extracted field(s): primary_patient_name. Cannot auto-decide;
  - ✓ policy_evaluation (PASSED) — 0ms
    - ✓ category_coverage: Category 'CONSULTATION' is covered.
    - ✓ submission_deadline: Claim assumed submitted within 30-day deadline of treatment date 2024-10-18.
    - ✓ minimum_claim_amount: Claimed ₹8000.0. Minimum: ₹500.0.
    - ✗ exclusion_check: Treatment/diagnosis matches exclusion: 'Obesity and weight loss programs'. This is not covered under
  - ✓ fraud_detection (PASSED) — 0ms
    - ✓ same_day_claims: No claims history provided. Cannot assess same-day pattern.
    - ✓ high_value_claim: Claimed amount ₹8,000 below threshold ₹25,000.
    - ✓ monthly_claims: No claims history provided.

---
