"""
Shared state schema for the LangGraph agent chain.

This is the object that flows through every node (router -> search ->
reasoning). Each node reads what it needs and writes back its result --
LangGraph merges these updates automatically between node calls.

Only records that Phase 2's deterministic matcher marked "needs_review" or
"exception" ever enter this graph. Everything here is about ONE invoice's
reconciliation chain at a time (invoice -> payment -> bank_transaction).
"""

from typing import TypedDict, Optional


class SearchAttempt(TypedDict):
    """One tool call the search agent made, kept for the audit trail."""
    tool_name: str
    arguments: dict
    result_count: int


class ReconciliationState(TypedDict):
    # --- input, set once before the graph runs ---
    invoice_id: str
    invoice_number: str
    invoice_amount: float
    invoice_date: str          # ISO string
    customer_name: str

    # what Phase 2 already found, if anything, and WHY it wasn't confident
    # -- gives the router/reasoning agents a head start instead of
    # starting blind.
    phase2_hop1_status: str
    phase2_hop2_status: Optional[str]
    phase2_matched_payment_id: Optional[str]
    phase2_matched_bank_txn_id: Optional[str]
    phase2_reasons: list[str]

    # --- router agent writes this ---
    route_target: Optional[str]        # "payment" | "bank_transaction" | "both"
    route_rationale: Optional[str]

    # --- search agent writes this ---
    search_attempts: list[SearchAttempt]
    candidate_payments: list[dict]
    candidate_bank_txns: list[dict]

    # --- reasoning agent writes this (the final output of the graph) ---
    final_status: Optional[str]        # "resolved_match" | "human_review" | "exception"
    confidence: Optional[float]
    justification: Optional[str]
    exception_category: Optional[str]  # only set if final_status == "exception"