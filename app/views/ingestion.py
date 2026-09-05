"""
Ingestion page — same Phase 1 logic as before (generate/upload, validate,
load to DB), restyled into cards to match the new visual system.
"""

import streamlit as st

from pathlib import Path

from finance_controller.db.repository import load_dataframe, get_all_counts, clear_all_tables
from finance_controller.ingestion.synthetic import generate_synthetic_batch
from finance_controller.ingestion.loaders import load_file_to_dataframe, UnsupportedFileTypeError
from finance_controller.ingestion.validators import validate_dataframe, coerce_dataframe
from finance_controller.utils.logger import new_run_id, log_event

TABLE_KEYS = ["invoice", "payment", "bank_transaction"]

if "run_id" not in st.session_state:
    st.session_state.run_id = new_run_id()
if "raw_data" not in st.session_state:
    st.session_state.raw_data = {}
if "validation_results" not in st.session_state:
    st.session_state.validation_results = {}

st.title("Ingestion")
st.caption("Bring in invoice, payment, and bank transaction data")


with st.container(border=True):
    st.subheader("Reset")
    counts = get_all_counts()
    total_staged = sum(counts.values())
    c1, c2 = st.columns([3, 1])
    c1.write(f"Currently staged: **{total_staged}** row(s) across all tables.")
    if c2.button("Reset database", disabled=(total_staged == 0)):
        deleted = clear_all_tables()
        report_path = Path("data/processed/final_report.csv")
        if report_path.exists():
            report_path.unlink()
        st.session_state.raw_data = {}
        st.session_state.validation_results = {}
        st.session_state.pop("last_report", None)
        st.session_state.pop("ground_truth", None)
        st.session_state.pop("data_source", None)
        log_event(st.session_state.run_id, "ingestion", "database_reset", rows_deleted=deleted)
        st.success(f"Cleared: {deleted}")
        st.rerun()


with st.container(border=True):
    st.subheader("1. Get data")
    source_mode = st.radio("Data source", ["Generate synthetic batch", "Upload files"], horizontal=True)

    if source_mode == "Generate synthetic batch":
        if st.button("Generate synthetic data", type="primary"):
            batch = generate_synthetic_batch()
            st.session_state.raw_data = {k: batch[k] for k in TABLE_KEYS}
            st.session_state.ground_truth = batch["ground_truth"]
            st.session_state.validation_results = {}
            st.session_state.data_source = "synthetic"
            log_event(st.session_state.run_id, "ingestion", "synthetic_generated",
                      row_counts={k: len(batch[k]) for k in TABLE_KEYS})
            st.success("Synthetic batch generated.")
    else:
        st.caption("Upload one file per table. Column names must match the expected schema.")
        cols = st.columns(3)
        for col, table_key in zip(cols, TABLE_KEYS):
            with col:
                uploaded = st.file_uploader(f"{table_key}.csv / .xlsx", type=["csv", "xlsx"], key=f"uploader_{table_key}")
                if uploaded is not None:
                    try:
                        df = load_file_to_dataframe(uploaded)
                        st.session_state.raw_data[table_key] = df
                        st.session_state.validation_results.pop(table_key, None)
                        st.session_state.data_source = "uploaded"
                        log_event(st.session_state.run_id, "ingestion", "file_uploaded",
                                  table_key=table_key, filename=uploaded.name, row_count=len(df))
                        st.success(f"Loaded {len(df)} rows")
                    except UnsupportedFileTypeError as e:
                        st.error(str(e))

st.write("")


if st.session_state.raw_data:
    with st.container(border=True):
        st.subheader("2. Preview & validate")
        for table_key in TABLE_KEYS:
            if table_key not in st.session_state.raw_data:
                continue
            df = st.session_state.raw_data[table_key]
            with st.expander(f"{table_key} — {len(df)} rows", expanded=False):
                st.dataframe(df.head(10), use_container_width=True)
                if st.button(f"Validate {table_key}", key=f"validate_{table_key}"):
                    result = validate_dataframe(table_key, df)
                    st.session_state.validation_results[table_key] = result
                    log_event(st.session_state.run_id, "validation",
                              "validation_passed" if result.is_valid else "validation_failed",
                              table_key=table_key, errors=result.errors, warnings=result.warnings)

                result = st.session_state.validation_results.get(table_key)
                if result is not None:
                    (st.success if result.is_valid else st.error)(result.summary())
                    for w in result.warnings:
                        st.warning(w)
                    for e in result.errors:
                        st.error(e)

    st.write("")

    # --- Step 3 ---
    all_valid = st.session_state.raw_data and all(
        st.session_state.validation_results.get(k) is not None and st.session_state.validation_results[k].is_valid
        for k in st.session_state.raw_data
    )
    with st.container(border=True):
        st.subheader("3. Load to database")
        if not all_valid:
            st.info("Validate every table above (with no errors) before loading.")
        else:
            if st.button("Load all tables into staging database", type="primary"):
                loaded_counts = {}
                for table_key, df in st.session_state.raw_data.items():
                    clean_df = coerce_dataframe(table_key, df)
                    loaded_counts[table_key] = load_dataframe(table_key, clean_df, replace=True)
                log_event(st.session_state.run_id, "db_load", "batch_loaded", row_counts=loaded_counts)
                st.success(f"Loaded: {loaded_counts}")
                st.balloons()

st.write("")
with st.container(border=True):
    st.subheader("Current database state")
    counts = get_all_counts()
    cols = st.columns(len(counts))
    for col, (table_key, count) in zip(cols, counts.items()):
        col.metric(table_key, count)

st.caption(f"Run ID: `{st.session_state.run_id}`")