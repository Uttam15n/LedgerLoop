"""
Pipeline — runs BOTH reconciliation hops and rolls them up into one
final status per invoice. This is the file that produces the actual
"match rate + exceptions" report the whole project is graded on.

    invoice --Hop1--> payment --Hop2--> bank_transaction

A single invoice's final status depends on BOTH hops:
    - fully_reconciled : hop1 auto_matched AND hop2 auto_matched
    - needs_review      : at least one hop is human_review/duplicate_candidate,
                            neither hop is a hard no_match
    - exception          : at least one hop is no_match (broken chain)

No LLM calls anywhere in this file -- this is Phase 2, purely deterministic.
Phase 3 (agents/) will later take the "needs_review" and "exception" buckets
and attempt to resolve them further via targeted, read-only SQL search +
reasoning.
"""

from dataclasses import dataclass

import pandas as pd

from finance_controller.matching.matcher import match_one_to_one, ColumnMapping, MatchOutcome

HOP1_MAPPING = ColumnMapping(
    source_id_col="invoice_id", target_id_col="payment_id",
    source_ref_col="invoice_number", target_ref_col="invoice_reference",
    source_amount_col="amount", target_amount_col="amount",
    source_date_col="date", target_date_col="date",
)

HOP2_MAPPING = ColumnMapping(
    source_id_col="payment_id", target_id_col="bank_txn_id",
    source_ref_col="utr", target_ref_col="utr_reference",
    source_amount_col="amount", target_amount_col="amount",
    source_date_col="date", target_date_col="date",
    source_text_col="payer_vpa", target_text_col="description",
)

# hop status -> how "bad" it is, used to roll two hop statuses into one.
_SEVERITY = {"auto_matched": 0, "human_review": 1, "duplicate_candidate": 2, "no_match": 3}


@dataclass
class ReconciliationResult:
    invoice_id: str
    final_status: str          # "fully_reconciled" | "needs_review" | "exception"
    hop1_status: str
    hop2_status: str | None    # None if hop1 itself failed (no payment to chain onward)
    matched_payment_id: str | None
    matched_bank_txn_id: str | None
    reasons: list[str]


def _roll_up_status(hop1_status: str, hop2_status: str | None) -> str:
    if hop1_status == "no_match":
        return "exception"          # no payment at all -> broken chain, full stop
    if hop2_status is None:
        return "exception"          # had a payment but couldn't even look for a bank hit
    if hop2_status == "no_match":
        return "exception"          # payment exists, bank never confirmed it

    worst = max(_SEVERITY[hop1_status], _SEVERITY[hop2_status])
    if worst == 0:
        return "fully_reconciled"
    return "needs_review"           # human_review or duplicate_candidate on either hop


def run_reconciliation(
    invoice_df: pd.DataFrame,
    payment_df: pd.DataFrame,
    bank_df: pd.DataFrame,
) -> list[ReconciliationResult]:
    """
    Run hop1 (invoice<->payment) then hop2 (payment<->bank_transaction) for
    whichever payments hop1 actually matched, and roll up one final status
    per invoice.
    """
    hop1_outcomes = match_one_to_one(invoice_df, payment_df, HOP1_MAPPING)
    hop1_by_invoice: dict[str, MatchOutcome] = {o.source_id: o for o in hop1_outcomes}

    # Only chase hop2 for payments that hop1 actually connected to an invoice --
    # no point scoring bank matches for a payment nobody claimed.
    matched_payment_ids = {
        o.matched_target_id for o in hop1_outcomes if o.matched_target_id is not None
    }
    relevant_payments = payment_df[payment_df["payment_id"].isin(matched_payment_ids)]

    hop2_outcomes = match_one_to_one(relevant_payments, bank_df, HOP2_MAPPING)
    hop2_by_payment: dict[str, MatchOutcome] = {o.source_id: o for o in hop2_outcomes}

    results = []
    for invoice_id, hop1 in hop1_by_invoice.items():
        reasons = []
        if hop1.best_score:
            reasons.extend(hop1.best_score.reasons)

        hop2 = None
        matched_bank_id = None
        if hop1.matched_target_id is not None:
            hop2 = hop2_by_payment.get(hop1.matched_target_id)
            if hop2:
                matched_bank_id = hop2.matched_target_id
                if hop2.best_score:
                    reasons.extend(hop2.best_score.reasons)

        final_status = _roll_up_status(hop1.status, hop2.status if hop2 else None)

        results.append(ReconciliationResult(
            invoice_id=invoice_id,
            final_status=final_status,
            hop1_status=hop1.status,
            hop2_status=hop2.status if hop2 else None,
            matched_payment_id=hop1.matched_target_id,
            matched_bank_txn_id=matched_bank_id,
            reasons=reasons,
        ))

    return results


def summarize(results: list[ReconciliationResult]) -> dict:
    """Simple counts by final_status -- the headline numbers for the report."""
    counts = {"fully_reconciled": 0, "needs_review": 0, "exception": 0}
    for r in results:
        counts[r.final_status] += 1
    total = len(results)
    match_rate = counts["fully_reconciled"] / total if total else 0.0
    return {"total": total, "counts": counts, "auto_match_rate": round(match_rate, 4)}