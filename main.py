"""
Full end-to-end run: Phase 1 data -> Phase 2 deterministic matcher ->
Phase 3 agent chain (real Groq calls) -> Phase 4 final report.

This is the real deliverable. Run this to get your actual match rate,
resolution rate, and categorized exception list.

Run with:
    python run_full_pipeline.py

Requires:
    - GROQ_API_KEY set (via .env)
    - pip install -e ".[agents]" already done
"""

from finance_controller.ingestion.synthetic import generate_synthetic_batch, save_synthetic_batch_to_raw
from finance_controller.matching.pipeline import run_reconciliation
from finance_controller.agents.graph import run_agent_chain
from finance_controller.reporting.report import build_report
from finance_controller.reporting.evaluation import evaluate_against_ground_truth
from finance_controller.db.session import init_db
from finance_controller.db.repository import load_dataframe
from finance_controller.ingestion.validators import coerce_dataframe

print("Generating synthetic batch (55+ invoices)...")
batch = generate_synthetic_batch()
invoice, payment, bank, ground_truth = batch["invoice"], batch["payment"], batch["bank_transaction"], batch["ground_truth"]
save_synthetic_batch_to_raw(batch)

print("Loading into staging database (so agent search tools have real data)...")
init_db()
for key, df in (("invoice", invoice), ("payment", payment), ("bank_transaction", bank)):
    load_dataframe(key, coerce_dataframe(key, df), replace=True)

print("Running Phase 2: deterministic matcher...")
phase2_results = run_reconciliation(invoice, payment, bank)
escalated = [r for r in phase2_results if r.final_status in ("needs_review", "exception")]
print(f"  {len(phase2_results) - len(escalated)}/{len(phase2_results)} auto-resolved deterministically")
print(f"  {len(escalated)} escalated to the agent chain")

print(f"Running Phase 3: agent chain on {len(escalated)} escalated records (this calls Groq, may take a bit)...")
phase3_outcomes = run_agent_chain(escalated, invoice)

print("Building final report...")
report = build_report(phase2_results, phase3_outcomes)
print()
report.print_summary()

# Save the detailed row-by-row report for inspection
df = report.to_dataframe()
df.to_csv("data/processed/final_report.csv", index=False)
print()
print("Detailed per-invoice report saved to data/processed/final_report.csv")

# Ground-truth evaluation -- this is the REAL measured-accuracy number,
# scored against the synthetic data's known answer key (never seen by
# the matcher or agents), not just self-reported bucket counts.
print()
print("Scoring against ground truth...")
evaluation = evaluate_against_ground_truth(df, ground_truth)
print()
evaluation.print_summary()
evaluation.mismatches.to_csv("data/processed/evaluation_mismatches.csv", index=False)
print()
print("Mismatches (if any) saved to data/processed/evaluation_mismatches.csv")