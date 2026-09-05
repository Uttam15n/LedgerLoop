"""
Dashboard — landing page. Shows current database status and, if a
reconciliation has been run, the last report's headline numbers via
the ledger strip.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from finance_controller.db.repository import get_all_counts
from app.theme import ledger_strip, COLORS

st.title("Dashboard")
st.caption("AI Finance Controller — reconciliation status at a glance")

st.write("")


with st.container(border=True):
    st.subheader("Staging database")
    counts = get_all_counts()
    cols = st.columns(3)
    labels = {"invoice": "Invoices", "payment": "Payments", "bank_transaction": "Bank transactions"}
    for col, (key, count) in zip(cols, counts.items()):
        col.metric(labels.get(key, key), count)

    if sum(counts.values()) == 0:
        st.info("No data loaded yet. Go to **Ingestion** to generate or upload a batch.")
    else:
        st.caption("To clear all staged data and start a fresh test cycle, use **Reset database** on the Ingestion page.")

st.write("")


with st.container(border=True):
    st.subheader("Last reconciliation run")

    report_path = Path("data/processed/final_report.csv")
    if not report_path.exists():
        st.info("No reconciliation has been run yet. Go to **Reconciliation** to run one.")
    else:
        df = pd.read_csv(report_path)
        bucket_counts = df["bucket"].value_counts().to_dict()
        auto = bucket_counts.get("auto_approved", 0)
        review = bucket_counts.get("human_review", 0)
        exception = bucket_counts.get("exception", 0)
        total = len(df)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total invoices", total)
        m2.metric("Final resolution rate", f"{auto/total:.1%}" if total else "—")
        phase2_count = (df["resolution_path"] == "phase2_deterministic").sum()
        m3.metric("Resolved with zero LLM cost", f"{phase2_count/total:.1%}" if total else "—")

        st.write("")
        ledger_strip(auto, review, exception)

        if exception > 0:
            st.write("")
            st.caption(f"{exception} record(s) need attention:")
            exc_df = df[df["bucket"] == "exception"][["invoice_id", "exception_category", "justification"]]
            st.dataframe(exc_df, use_container_width=True, hide_index=True)