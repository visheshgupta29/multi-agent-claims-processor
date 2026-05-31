"""Eval harness — runs all 12 test cases and generates a report.

Usage:
    python -m eval.runner
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.claim import (
    ClaimRequest,
    DocumentInput,
    DocumentType,
    DocumentQuality,
    ClaimCategory,
    ClaimHistoryItem,
)
from app.pipeline.graph import process_claim


def load_test_cases(path: str = None) -> list[dict]:
    """Load test cases from JSON file."""
    if path is None:
        candidates = [
            Path(__file__).parent.parent.parent / "test_cases.json",
            Path(__file__).parent.parent / "test_cases.json",
            Path("test_cases.json"),
        ]
        for p in candidates:
            if p.exists():
                path = str(p)
                break
        else:
            raise FileNotFoundError("test_cases.json not found")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["test_cases"]


def build_claim_request(test_case: dict) -> ClaimRequest:
    """Convert a test case input into a ClaimRequest."""
    inp = test_case["input"]

    # Build documents
    documents = []
    for doc_data in inp.get("documents", []):
        doc = DocumentInput(
            file_id=doc_data.get("file_id", ""),
            file_name=doc_data.get("file_name", ""),
            actual_type=DocumentType(doc_data["actual_type"]) if doc_data.get("actual_type") else None,
            quality=DocumentQuality(doc_data["quality"]) if doc_data.get("quality") else None,
            patient_name_on_doc=doc_data.get("patient_name_on_doc"),
            content=doc_data.get("content"),
        )
        documents.append(doc)

    # Build claims history
    claims_history = []
    for hist in inp.get("claims_history", []):
        claims_history.append(ClaimHistoryItem(**hist))

    return ClaimRequest(
        member_id=inp["member_id"],
        policy_id=inp.get("policy_id", "PLUM_GHI_2024"),
        claim_category=ClaimCategory(inp["claim_category"]),
        treatment_date=inp["treatment_date"],
        claimed_amount=inp["claimed_amount"],
        hospital_name=inp.get("hospital_name"),
        ytd_claims_amount=inp.get("ytd_claims_amount", 0),
        documents=documents,
        claims_history=claims_history,
        simulate_component_failure=inp.get("simulate_component_failure", False),
    )


def evaluate_result(test_case: dict, decision) -> dict:
    """Compare actual decision against expected outcome."""
    expected = test_case["expected"]
    result = {
        "case_id": test_case["case_id"],
        "case_name": test_case["case_name"],
        "expected_decision": expected.get("decision"),
        "actual_decision": decision.decision.value if decision.decision else None,
        "expected_amount": expected.get("approved_amount"),
        "actual_amount": decision.approved_amount,
        "passed": True,
        "notes": [],
    }

    # Check decision match
    exp_decision = expected.get("decision")
    act_decision = decision.decision.value if decision.decision else None

    if exp_decision != act_decision:
        # Special case: expected null decision means halt
        if exp_decision is None and act_decision is None:
            result["notes"].append("Both expected and actual are HALT (no decision) — PASS")
        else:
            result["passed"] = False
            result["notes"].append(f"Decision mismatch: expected {exp_decision}, got {act_decision}")

    # Check amount (if applicable)
    if expected.get("approved_amount") is not None:
        if decision.approved_amount != expected["approved_amount"]:
            result["passed"] = False
            result["notes"].append(
                f"Amount mismatch: expected ₹{expected['approved_amount']}, got ₹{decision.approved_amount}"
            )

    # Check system_must requirements
    for requirement in expected.get("system_must", []):
        result["notes"].append(f"[REQUIREMENT] {requirement}")

    # Check rejection reasons
    if expected.get("rejection_reasons"):
        for reason in expected["rejection_reasons"]:
            if reason not in decision.rejection_reasons:
                result["passed"] = False
                result["notes"].append(f"Missing rejection reason: {reason}")

    # Check confidence
    if expected.get("confidence_score"):
        threshold_str = expected["confidence_score"]
        if "above" in threshold_str:
            threshold = float(threshold_str.split("above")[1].strip())
            if decision.confidence_score <= threshold:
                result["passed"] = False
                result["notes"].append(
                    f"Confidence too low: expected above {threshold}, got {decision.confidence_score}"
                )

    return result


def generate_report(results: list[dict], decisions: list) -> str:
    """Generate a markdown evaluation report."""
    lines = []
    lines.append("# Evaluation Report")
    lines.append(f"\nGenerated: {datetime.utcnow().isoformat()}")
    lines.append(f"\n## Summary\n")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    lines.append(f"**{passed}/{total} test cases passed**\n")

    # Results table
    lines.append("| Case | Name | Expected | Actual | Amount (Expected/Actual) | Status |")
    lines.append("|------|------|----------|--------|--------------------------|--------|")

    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        exp_dec = r["expected_decision"] or "HALT"
        act_dec = r["actual_decision"] or "HALT"
        exp_amt = f"₹{r['expected_amount']:,.0f}" if r["expected_amount"] else "—"
        act_amt = f"₹{r['actual_amount']:,.0f}" if r["actual_amount"] else "—"
        lines.append(f"| {r['case_id']} | {r['case_name']} | {exp_dec} | {act_dec} | {exp_amt} / {act_amt} | {status} |")

    # Detailed results
    lines.append("\n---\n")
    lines.append("## Detailed Results\n")

    for i, (r, decision) in enumerate(zip(results, decisions)):
        lines.append(f"### {r['case_id']}: {r['case_name']}\n")
        lines.append(f"**Status:** {'✅ PASS' if r['passed'] else '❌ FAIL'}")
        lines.append(f"\n**Decision:** {r['actual_decision'] or 'HALT (no decision)'}")
        if decision and decision.approved_amount is not None:
            lines.append(f"\n**Approved Amount:** ₹{decision.approved_amount:,.0f}")
        if decision:
            lines.append(f"\n**Confidence:** {decision.confidence_score}")

        if decision and decision.error_message:
            lines.append(f"\n**Error Message:**\n> {decision.error_message}")

        if decision and decision.explanation:
            lines.append(f"\n**Explanation:**\n```\n{decision.explanation}\n```")

        if r["notes"]:
            lines.append("\n**Notes:**")
            for note in r["notes"]:
                lines.append(f"- {note}")

        # Trace summary
        if decision and decision.trace and decision.trace.steps:
            lines.append("\n**Trace Steps:**")
            for step in decision.trace.steps:
                status_icon = {"PASSED": "✓", "FAILED": "✗", "ERROR": "⚠", "SKIPPED": "○"}
                icon = status_icon.get(step.status.value, "?")
                lines.append(f"  - {icon} {step.step_name} ({step.status.value}) — {step.duration_ms}ms")
                for check in step.checks_performed:
                    check_icon = "✓" if check.result == "PASS" else "✗"
                    lines.append(f"    - {check_icon} {check.check_name}: {check.details[:100]}")

        lines.append("\n---\n")

    return "\n".join(lines)


async def run_eval():
    """Run all test cases and generate report."""
    print("Loading test cases...")
    test_cases = load_test_cases()
    print(f"Found {len(test_cases)} test cases.\n")

    results = []
    decisions = []

    for tc in test_cases:
        case_id = tc["case_id"]
        print(f"Running {case_id}: {tc['case_name']}... ", end="")

        try:
            request = build_claim_request(tc)
            decision = await process_claim(request)
            result = evaluate_result(tc, decision)
            results.append(result)
            decisions.append(decision)

            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            dec_str = decision.decision.value if decision.decision else "HALT"
            print(f"{status} (decision: {dec_str})")

        except Exception as e:
            print(f"💥 ERROR: {e}")
            results.append({
                "case_id": case_id,
                "case_name": tc["case_name"],
                "expected_decision": tc["expected"].get("decision"),
                "actual_decision": "ERROR",
                "expected_amount": tc["expected"].get("approved_amount"),
                "actual_amount": None,
                "passed": False,
                "notes": [f"Exception: {str(e)}"],
            })
            decisions.append(None)

    # Generate report
    report = generate_report(results, decisions)

    # Save report
    report_path = Path(__file__).parent / "eval_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Report saved to: {report_path}")
    print(f"Results: {sum(1 for r in results if r['passed'])}/{len(results)} passed")

    return results


if __name__ == "__main__":
    asyncio.run(run_eval())
