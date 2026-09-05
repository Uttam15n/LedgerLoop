"""
Reconciliation page — reads whatever is currently staged in the database
(loaded via the Ingestion page), shows which records need agent
verification, runs the batch, and displays a downloadable report.

A secondary "verify one invoice manually" tool sits at the bottom, for
spot-checking a specific record outside the main bulk flow.
"""

import pandas as pd
import streamlit as st

from finance_controller.db.repository import get_all
from finance_controller.matching.pipeline import run_reconciliation
from finance_controller.agents.graph import run_agent_chain, verify_single_record
from finance_controller.reporting.report import build_report
from finance_controller.reporting.evaluation import evaluate_against_ground_truth
from app.theme import ledger_strip, status_badge

st.title("Reconciliation")
st.caption("Run the deterministic matcher, then escalate ambiguous records to the agent chain")

invoice_df = get_all("invoice")
payment_df = get_all("payment")
bank_df = get_all("bank_transaction")

if invoice_df.empty:
    st.warning("No data in the staging database yet. Go to **Ingestion** to generate or upload a batch first.")
    st.stop()

for df in (invoice_df, payment_df, bank_df):
    if not str(df["date"].dtype).startswith("datetime"):
        df["date"] = pd.to_datetime(df["date"])

data_source = st.session_state.get("data_source", "unknown")
source_label = {"synthetic": "Synthetic (generated)", "uploaded": "Uploaded by you", "unknown": "Unknown source"}

# Phase 2 is pure, deterministic pandas/numpy -- no LLM, cheap to run.
# Recompute fresh on every page load so it always reflects whatever is
# CURRENTLY staged, never a stale cache from a previous dataset.
phase2_results = run_reconciliation(invoice_df, payment_df, bank_df)
phase2_by_invoice = {r.invoice_id: r for r in phase2_results}
escalated = [r for r in phase2_results if r.final_status in ("needs_review", "exception")]


with st.container(border=True):
    st.subheader("Run full batch")
    st.caption(f"Verifying **{len(invoice_df)}** invoices — data source: **{source_label.get(data_source, data_source)}**")

    st.write(
        f"Phase 2 auto-resolves **{len(invoice_df) - len(escalated)}** deterministically; "
        f"**{len(escalated)}** need the agent chain."
    )

    if escalated:
        with st.expander(f"Records to be verified by the agent chain ({len(escalated)})", expanded=False):
            preview_df = pd.DataFrame([
                {
                    "invoice_id": r.invoice_id,
                    "hop1_status": r.hop1_status,
                    "hop2_status": r.hop2_status,
                    "reason": "; ".join(r.reasons) if r.reasons else "—",
                }
                for r in escalated
            ])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Nothing needs verification — Phase 2 resolved every record.")

    c1, c2 = st.columns([3, 1])
    delay = c2.number_input("Delay/record (s)", min_value=0.0, max_value=5.0, value=1.0, step=0.5,
                             help="Spacing between Groq calls, to avoid rate limits.")
    run_clicked = c1.button("Run reconciliation", type="primary")

if run_clicked:
    progress_placeholder = st.empty()

    def _on_progress(index, total, invoice_id, final_state):
        progress_placeholder.info(
            f"Verifying record {index + 1} of {total}: **{invoice_id}** → `{final_state['final_status']}`"
        )

    if escalated:
        progress_placeholder.info(f"Starting verification of {len(escalated)} record(s)...")
        phase3_outcomes = run_agent_chain(
            escalated, invoice_df, delay_between_records_seconds=delay, on_progress=_on_progress,
        )
    else:
        phase3_outcomes = []

    progress_placeholder.info("Building report...")
    report = build_report(phase2_results, phase3_outcomes)
    report.to_dataframe().to_csv("data/processed/final_report.csv", index=False)
    st.session_state.last_report = report

    progress_placeholder.empty()
    st.success("Reconciliation complete — see report below.")


report = st.session_state.get("last_report")

if report is not None:
    st.write("")
    with st.container(border=True):
        st.subheader("Results")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total invoices", report.total)
        m2.metric("Phase 2 auto-match rate", f"{report.auto_match_rate:.1%}")
        m3.metric("Final resolution rate", f"{report.final_resolution_rate:.1%}")

        st.write("")
        ledger_strip(
            report.bucket_counts.get("auto_approved", 0),
            report.bucket_counts.get("human_review", 0),
            report.bucket_counts.get("exception", 0),
        )

        if report.exception_category_counts:
            st.write("")
            st.caption("Exception categories")
            cols = st.columns(len(report.exception_category_counts))
            for col, (cat, count) in zip(cols, report.exception_category_counts.items()):
                col.metric(cat.replace("_", " ").title(), count)

        st.write("")
        st.caption("Agent chain stats")
        s1, s2, s3 = st.columns(3)
        s1.metric("Escalated to agents", report.phase3_stats["records_escalated_to_agent_chain"])
        s2.metric("Resolved by agents", report.phase3_stats["additionally_resolved_by_agents"])
        s3.metric("Search tool calls", report.phase3_stats["total_search_tool_calls"])

    st.write("")
    with st.container(border=True):
        st.subheader("Per-invoice detail")
        df = report.to_dataframe()
        bucket_filter = st.multiselect("Filter by bucket", options=df["bucket"].unique().tolist(),
                                        default=df["bucket"].unique().tolist())
        filtered = df[df["bucket"].isin(bucket_filter)]
        st.dataframe(
            filtered[["invoice_id", "bucket", "resolution_path", "confidence", "exception_category", "justification"]],
            use_container_width=True, hide_index=True,
        )

        st.download_button(
            "Download full report (CSV)",
            data=df.to_csv(index=False),
            file_name="reconciliation_report.csv",
            mime="text/csv",
        )

   
    ground_truth = st.session_state.get("ground_truth")
    if ground_truth is not None:
        st.write("")
        with st.container(border=True):
            st.subheader("Evaluation against ground truth")
            st.caption(
                "This measures how often the system's decision was actually correct, "
                "scored against the synthetic data's known answer key — not just self-reported buckets."
            )

            evaluation = evaluate_against_ground_truth(df, ground_truth)

            e1, e2 = st.columns(2)
            e1.metric("Overall accuracy", f"{evaluation.overall_accuracy:.1%}")
            e2.metric("Records scored", evaluation.total_records)

            st.write("")
            st.caption("Precision / recall per bucket")
            pr_cols = st.columns(3)
            for col, bucket in zip(pr_cols, ["auto_approved", "human_review", "exception"]):
                p = evaluation.per_bucket_precision.get(bucket, float("nan"))
                r = evaluation.per_bucket_recall.get(bucket, float("nan"))
                col.metric(bucket.replace("_", " ").title(), f"P {p:.0%} / R {r:.0%}")

            st.write("")
            st.caption("Confusion matrix (rows = expected, columns = actual)")
            st.dataframe(evaluation.confusion_matrix, use_container_width=True)

            st.write("")
            st.caption("Accuracy by synthetic case type")
            st.dataframe(evaluation.per_case_type_accuracy, use_container_width=True)

            if not evaluation.mismatches.empty:
                st.write("")
                with st.expander(f"{len(evaluation.mismatches)} mismatch(es)"):
                    st.dataframe(
                        evaluation.mismatches[["invoice_id", "case_type", "expected_bucket", "actual_bucket"]],
                        use_container_width=True, hide_index=True,
                    )
    else:
        st.caption(
            "Ground-truth evaluation is only available when synthetic data was generated "
            "(the known answer key isn't available for your own uploaded data)."
        )


st.write("")
with st.expander("Verify a specific invoice manually"):
    st.caption("Pick any invoice and see the agent chain's full reasoning for it, live.")

    all_ids = invoice_df["invoice_id"].tolist()
    selected_id = st.selectbox("Invoice", options=all_ids, index=0)

    phase2_row = phase2_by_invoice.get(selected_id)
    if phase2_row:
        st.caption(
            f"Phase 2 status — hop1: `{phase2_row.hop1_status}`, "
            f"hop2: `{phase2_row.hop2_status}`, final: `{phase2_row.final_status}`"
        )

    if st.button("Verify with AI"):
        invoice_row = invoice_df[invoice_df["invoice_id"] == selected_id].iloc[0]
        with st.spinner("Router → search → reasoning..."):
            result_state = verify_single_record(phase2_row, invoice_row)

        st.write("")
        st.markdown(status_badge(
            "auto_approved" if result_state["final_status"] == "resolved_match"
            else result_state["final_status"]
        ), unsafe_allow_html=True)
        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Router decision**")
            st.write(f"Target: `{result_state['route_target']}`")
            st.caption(result_state["route_rationale"])
        with c2:
            st.markdown("**Confidence**")
            st.write(f"{result_state['confidence']:.0%}" if result_state["confidence"] is not None else "—")

        st.markdown("**Search attempts**")
        if result_state["search_attempts"]:
            st.dataframe(pd.DataFrame(result_state["search_attempts"]), use_container_width=True, hide_index=True)
        else:
            st.caption("No search needed.")

        c3, c4 = st.columns(2)
        with c3:
            st.markdown(f"**Candidate payments** ({len(result_state['candidate_payments'])})")
            if result_state["candidate_payments"]:
                st.dataframe(pd.DataFrame(result_state["candidate_payments"]), use_container_width=True, hide_index=True)
        with c4:
            st.markdown(f"**Candidate bank transactions** ({len(result_state['candidate_bank_txns'])})")
            if result_state["candidate_bank_txns"]:
                st.dataframe(pd.DataFrame(result_state["candidate_bank_txns"]), use_container_width=True, hide_index=True)

        st.markdown("**Reasoning**")
        st.info(result_state["justification"])
        if result_state["exception_category"]:
            st.caption(f"Exception category: `{result_state['exception_category']}`")