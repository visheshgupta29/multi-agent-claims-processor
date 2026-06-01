"""Streamlit UI for Health Insurance Claims Processing System."""

import asyncio
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from app.models.claim import (
    ClaimRequest,
    DocumentInput,
    DocumentType,
    DocumentQuality,
    ClaimCategory,
    ClaimHistoryItem,
)
from app.pipeline.graph import process_claim


st.set_page_config(
    page_title="Plum Claims Processor",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 Health Insurance Claims Processing")
st.caption("Multi-agent AI system for OPD claim adjudication")


# --- Sidebar: Test Case Loader ---
st.sidebar.header("Quick Load Test Case")

test_cases_path = Path(__file__).parent / "test_cases.json"
if test_cases_path.exists():
    with open(test_cases_path, "r") as f:
        test_data = json.load(f)
    case_options = {
        f"{tc['case_id']}: {tc['case_name']}": tc
        for tc in test_data["test_cases"]
    }
    selected_case = st.sidebar.selectbox(
        "Select a test case",
        options=["(Manual Entry)"] + list(case_options.keys()),
    )
else:
    test_data = None
    selected_case = "(Manual Entry)"
    st.sidebar.warning("test_cases.json not found")

# --- Main Form ---
st.header("Submit Claim")

col1, col2 = st.columns(2)

# Pre-populate from test case if selected
prefill = {}
if selected_case != "(Manual Entry)" and selected_case in case_options:
    prefill = case_options[selected_case]["input"]

with col1:
    member_id = st.text_input("Member ID", value=prefill.get("member_id", "EMP001"))
    category = st.selectbox(
        "Claim Category",
        options=[c.value for c in ClaimCategory],
        index=[c.value for c in ClaimCategory].index(prefill.get("claim_category", "CONSULTATION")),
    )
    treatment_date = st.text_input(
        "Treatment Date (YYYY-MM-DD)",
        value=prefill.get("treatment_date", "2024-11-01"),
    )

with col2:
    claimed_amount = st.number_input(
        "Claimed Amount (₹)",
        value=float(prefill.get("claimed_amount", 1500)),
        min_value=0.0,
        step=100.0,
    )
    ytd_claims = st.number_input(
        "YTD Claims Amount (₹)",
        value=float(prefill.get("ytd_claims_amount", 5000)),
        min_value=0.0,
        step=500.0,
    )
    hospital_name = st.text_input(
        "Hospital Name (optional)",
        value=prefill.get("hospital_name", ""),
    )

# Documents section
st.subheader("Documents")

doc_tab1, doc_tab2 = st.tabs(["📁 File Upload", "📝 JSON Input"])

uploaded_files_data = []

with doc_tab1:
    st.caption("Upload medical documents (images, PDFs). The system will extract data using Groq Vision.")
    uploaded_files = st.file_uploader(
        "Upload documents (JPG, PNG, PDF)",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
        key="doc_uploader",
    )

    if uploaded_files:
        for i, uploaded_file in enumerate(uploaded_files):
            col_type, col_info = st.columns([1, 2])
            with col_type:
                doc_type = st.selectbox(
                    f"Type for {uploaded_file.name}",
                    options=[dt.value for dt in DocumentType],
                    key=f"doc_type_{i}",
                )
            with col_info:
                st.caption(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

            file_bytes = uploaded_file.read()
            uploaded_file.seek(0)  # Reset for potential re-read
            uploaded_files_data.append({
                "file_id": f"UPLOAD_{i+1:03d}",
                "file_name": uploaded_file.name,
                "doc_type": doc_type,
                "file_data": file_bytes,
            })

with doc_tab2:
    if prefill.get("documents"):
        docs_json = json.dumps(prefill["documents"], indent=2)
    else:
        docs_json = json.dumps([
            {
                "file_id": "F001",
                "actual_type": "PRESCRIPTION",
                "patient_name_on_doc": "Rajesh Kumar",
                "content": {
                    "doctor_name": "Dr. Arun Sharma",
                    "doctor_registration": "KA/45678/2015",
                    "patient_name": "Rajesh Kumar",
                    "date": "2024-11-01",
                    "diagnosis": "Viral Fever",
                },
            },
            {
                "file_id": "F002",
                "actual_type": "HOSPITAL_BILL",
                "patient_name_on_doc": "Rajesh Kumar",
                "content": {
                    "hospital_name": "City Clinic",
                    "patient_name": "Rajesh Kumar",
                    "date": "2024-11-01",
                    "line_items": [{"description": "Consultation Fee", "amount": 1000}],
                    "total": 1500,
                },
            },
        ], indent=2)

    documents_text = st.text_area(
        "Documents (JSON array)",
        value=docs_json,
        height=250,
    )

# Claims history
with st.expander("Claims History (optional)"):
    if prefill.get("claims_history"):
        history_json = json.dumps(prefill["claims_history"], indent=2)
    else:
        history_json = "[]"
    claims_history_text = st.text_area(
        "Claims History (JSON array)",
        value=history_json,
        height=120,
    )

# Component failure simulation
simulate_failure = st.checkbox(
    "Simulate component failure (TC011)",
    value=prefill.get("simulate_component_failure", False),
)

# --- Submit ---
if st.button("🚀 Process Claim", type="primary", use_container_width=True):
    try:
        # Build documents from either file uploads or JSON
        documents = []

        if uploaded_files_data:
            # Use file upload path
            for upload in uploaded_files_data:
                documents.append(DocumentInput(
                    file_id=upload["file_id"],
                    file_name=upload["file_name"],
                    actual_type=DocumentType(upload["doc_type"]),
                    file_data=upload["file_data"],
                ))
        else:
            # Use JSON text input
            docs_data = json.loads(documents_text)
            for d in docs_data:
                documents.append(DocumentInput(
                    file_id=d.get("file_id", ""),
                    file_name=d.get("file_name", ""),
                    actual_type=DocumentType(d["actual_type"]) if d.get("actual_type") else None,
                    quality=DocumentQuality(d["quality"]) if d.get("quality") else None,
                    patient_name_on_doc=d.get("patient_name_on_doc"),
                    content=d.get("content"),
                ))

        # Parse claims history
        history_data = json.loads(claims_history_text)
        claims_history = [ClaimHistoryItem(**h) for h in history_data]

        # Build request
        request = ClaimRequest(
            member_id=member_id,
            claim_category=ClaimCategory(category),
            treatment_date=treatment_date,
            claimed_amount=claimed_amount,
            hospital_name=hospital_name or None,
            ytd_claims_amount=ytd_claims,
            documents=documents,
            claims_history=claims_history,
            simulate_component_failure=simulate_failure,
        )

        # Process
        with st.spinner("Processing claim through multi-agent pipeline..."):
            decision = asyncio.run(process_claim(request))

        # --- Results ---
        st.divider()
        st.header("Decision")

        # Decision badge
        decision_colors = {
            "APPROVED": "green",
            "PARTIAL": "orange",
            "REJECTED": "red",
            "MANUAL_REVIEW": "blue",
        }
        dec_val = decision.decision.value if decision.decision else "HALT"
        dec_color = decision_colors.get(dec_val, "gray")

        col_dec, col_amt, col_conf = st.columns(3)
        with col_dec:
            st.metric("Decision", dec_val)
        with col_amt:
            amt_str = f"₹{decision.approved_amount:,.0f}" if decision.approved_amount else "—"
            st.metric("Approved Amount", amt_str)
        with col_conf:
            st.metric("Confidence", f"{decision.confidence_score:.0%}")

        # Explanation
        if decision.explanation:
            st.subheader("Explanation")
            st.text(decision.explanation)

        # Error message (for HALT cases)
        if decision.error_message:
            st.error(f"**Error:** {decision.error_message}")

        # Line item decisions
        if decision.line_item_decisions:
            st.subheader("Line Item Decisions")
            for lid in decision.line_item_decisions:
                icon = "✅" if lid.approved else "❌"
                st.write(f"{icon} **{lid.description}** — ₹{lid.amount:,.0f} — {lid.reason}")

        # Fraud signals
        if decision.fraud_signals:
            st.subheader("⚠️ Fraud Signals")
            for sig in decision.fraud_signals:
                st.warning(f"**[{sig.severity}] {sig.signal_name}:** {sig.details}")

        # Trace
        if decision.trace:
            st.subheader("Pipeline Trace")
            trace = decision.trace
            st.caption(f"Claim ID: `{trace.claim_id}` | Total: {trace.total_duration_ms}ms")

            for step in trace.steps:
                status_icon = {"PASSED": "✅", "FAILED": "❌", "ERROR": "⚠️", "SKIPPED": "⏭️"}
                icon = status_icon.get(step.step_name and step.status.value, "❓")
                with st.expander(f"{icon} {step.step_name} ({step.status.value}) — {step.duration_ms}ms"):
                    if step.input_summary:
                        st.json(step.input_summary)
                    if step.output_summary:
                        st.json(step.output_summary)
                    if step.checks_performed:
                        for check in step.checks_performed:
                            check_icon = "✅" if check.result == "PASS" else "❌"
                            st.write(f"{check_icon} **{check.check_name}**: {check.details}")

        # Raw JSON
        with st.expander("📄 Raw Decision JSON"):
            st.json(decision.model_dump(mode="json"))

    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in documents or claims history: {e}")
    except Exception as e:
        st.error(f"Error processing claim: {e}")
        import traceback
        st.code(traceback.format_exc())
