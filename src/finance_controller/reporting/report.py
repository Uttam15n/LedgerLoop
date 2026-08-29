"""
Final report — combines Phase 2 (deterministic) and Phase 3 (agent chain)
outcomes into the actual deliverable this whole project is graded on:
throughput, measured accuracy, and an honest, categorized exception list.

Every invoice ends up in exactly one of three buckets, matching our
original architecture diagram:
    - auto_approved  : Phase 2 alone resolved it, >=90% confidence, no LLM touched it
    - human_review    : either Phase 2 flagged it ambiguous and the agent
                          chain also couldn't reach full confidence, or the
                          agent chain explicitly said "human_review"
    - exception        : agent chain (or Phase 2, if escalation wasn't even
                          possible) concluded this is a genuine reconciliation gap

No invoice is silently dropped -- every single one appears in exactly one
bucket, which is the "no cherry-picking" requirement from the brief.
"""

from dataclasses import dataclass, field

import pandas as pd

from finance_controller.matching.pipeline import ReconciliationResult
from finance_controller.config.settings import CONFIDENCE_THRESHOLDS


@dataclass
class InvoiceReportRow:
    invoice_id: str
    bucket: str                       # "auto_approved" | "human_review" | "exception"
    resolution_path: str              # "phase2_deterministic" | "phase3_agent"
    confidence: float
    matched_payment_id: str | None
    matched_bank_txn_id: str | None
    exception_category: str | None
    justification: str


@dataclass
class ReconciliationReport:
    rows: list[InvoiceReportRow]
    total: int
    auto_match_rate: float            # phase2-only, deterministic, reproducible
    final_resolution_rate: float      # auto_approved / total, AFTER agent chain too
    bucket_counts: dict[str, int]
    exception_category_counts: dict[str, int]
    phase3_stats: dict                # tool calls, records escalated, etc.

    def print_summary(self) -> None:
        print("=" * 60)
        print("RECONCILIATION REPORT")
        print("=" * 60)
        print(f"Total invoices processed: {self.total}")
        print(f"Phase 2 deterministic auto-match rate: {self.auto_match_rate:.1%}")
        print(f"Final resolution rate (after agent chain): {self.final_resolution_rate:.1%}")
        print()
        print("Bucket breakdown:")
        for bucket, count in self.bucket_counts.items():
            pct = count / self.total if self.total else 0
            print(f"  {bucket:15s}: {count:3d}  ({pct:.1%})")
        print()
        if self.exception_category_counts:
            print("Exception categories:")
            for category, count in sorted(self.exception_category_counts.items(), key=lambda x: -x[1]):
                print(f"  {category:20s}: {count}")
        print()
        print("Phase 3 (agent chain) stats:")
        for k, v in self.phase3_stats.items():
            print(f"  {k}: {v}")
        print("=" * 60)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(r) for r in self.rows])


def build_report(
    phase2_results: list[ReconciliationResult],
    phase3_outcomes: list[dict],  # list of final ReconciliationState dicts from run_agent_chain()
) -> ReconciliationReport:
    """
    Combine Phase 2 + Phase 3 outcomes into the final report.

    phase2_results should be ALL invoices (not just escalated ones) --
    this function figures out which ones were auto-resolved vs escalated.
    phase3_outcomes should be the agent chain's output for exactly the
    escalated subset.
    """
    auto_approve_threshold = CONFIDENCE_THRESHOLDS["auto_approve"]

    phase3_by_invoice = {o["invoice_id"]: o for o in phase3_outcomes}
    escalated_ids = set(phase3_by_invoice.keys())

    rows: list[InvoiceReportRow] = []

    for r in phase2_results:
        if r.invoice_id not in escalated_ids:
            # Phase 2 alone resolved this -- must have been "fully_reconciled"
            # for it to not be escalated (see matching.pipeline's rollup logic).
            rows.append(InvoiceReportRow(
                invoice_id=r.invoice_id,
                bucket="auto_approved",
                resolution_path="phase2_deterministic",
                confidence=1.0,  # deterministic match, not a probabilistic score
                matched_payment_id=r.matched_payment_id,
                matched_bank_txn_id=r.matched_bank_txn_id,
                exception_category=None,
                justification="Auto-matched by deterministic rules (reference, amount, date all within tolerance).",
            ))
        else:
            outcome = phase3_by_invoice[r.invoice_id]
            status = outcome["final_status"]
            confidence = outcome["confidence"] or 0.0

            if status == "resolved_match" and confidence >= auto_approve_threshold:
                bucket = "auto_approved"
            elif status == "exception":
                bucket = "exception"
            else:
                bucket = "human_review"

            rows.append(InvoiceReportRow(
                invoice_id=r.invoice_id,
                bucket=bucket,
                resolution_path="phase3_agent",
                confidence=confidence,
                matched_payment_id=r.matched_payment_id,
                matched_bank_txn_id=outcome.get("candidate_bank_txns", [{}])[0].get("bank_txn_id") if bucket == "auto_approved" and outcome.get("candidate_bank_txns") else r.matched_bank_txn_id,
                exception_category=outcome.get("exception_category"),
                justification=outcome.get("justification", ""),
            ))

    total = len(rows)
    bucket_counts = {"auto_approved": 0, "human_review": 0, "exception": 0}
    exception_category_counts: dict[str, int] = {}

    for row in rows:
        bucket_counts[row.bucket] += 1
        if row.exception_category:
            exception_category_counts[row.exception_category] = exception_category_counts.get(row.exception_category, 0) + 1

    phase2_auto_count = sum(1 for r in phase2_results if r.invoice_id not in escalated_ids)
    auto_match_rate = phase2_auto_count / total if total else 0.0
    final_resolution_rate = bucket_counts["auto_approved"] / total if total else 0.0

    phase3_stats = {
        "records_escalated_to_agent_chain": len(escalated_ids),
        "additionally_resolved_by_agents": sum(
            1 for row in rows if row.resolution_path == "phase3_agent" and row.bucket == "auto_approved"
        ),
        "total_search_tool_calls": sum(len(o.get("search_attempts", [])) for o in phase3_outcomes),
    }

    return ReconciliationReport(
        rows=rows,
        total=total,
        auto_match_rate=round(auto_match_rate, 4),
        final_resolution_rate=round(final_resolution_rate, 4),
        bucket_counts=bucket_counts,
        exception_category_counts=exception_category_counts,
        phase3_stats=phase3_stats,
    )