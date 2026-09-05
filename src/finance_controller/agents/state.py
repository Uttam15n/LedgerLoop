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
    
    invoice_id: str
    invoice_number: str
    invoice_amount: float
    invoice_date: str          
    customer_name: str

    
    phase2_hop1_status: str
    phase2_hop2_status: Optional[str]
    phase2_matched_payment_id: Optional[str]
    phase2_matched_bank_txn_id: Optional[str]
    phase2_reasons: list[str]

    
    route_target: Optional[str]        
    route_rationale: Optional[str]

    
    search_attempts: list[SearchAttempt]
    candidate_payments: list[dict]
    candidate_bank_txns: list[dict]

    
    final_status: Optional[str]        
    confidence: Optional[float]
    justification: Optional[str]
    exception_category: Optional[str]  