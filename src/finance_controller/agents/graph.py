"""
LangGraph wiring: router -> search -> reasoning.

The graph itself is intentionally linear (no conditional branching) --
every escalated record goes through all three nodes. Reasoning always
needs to run after search regardless of what the router decided, since
even "found nothing" is meaningful evidence the reasoning agent should
see and explain, not a reason to skip straight to a verdict.

build_initial_state() is the seam between Phase 2 (matching.pipeline)
and Phase 3 (this graph) -- it's what turns a ReconciliationResult +
its invoice row into the ReconciliationState this graph expects.
"""

from langgraph.graph import StateGraph, END

from finance_controller.agents.state import ReconciliationState
from finance_controller.agents.nodes import router_node, search_node, reasoning_node
from finance_controller.matching.pipeline import ReconciliationResult


def build_graph():
    """Compile the router -> search -> reasoning graph. Call once, reuse across records."""
    graph = StateGraph(ReconciliationState)

    graph.add_node("router", router_node)
    graph.add_node("search", search_node)
    graph.add_node("reasoning", reasoning_node)

    graph.set_entry_point("router")
    graph.add_edge("router", "search")
    graph.add_edge("search", "reasoning")
    graph.add_edge("reasoning", END)

    return graph.compile()


def build_initial_state(result: ReconciliationResult, invoice_row) -> ReconciliationState:
    """
    Turn a Phase 2 ReconciliationResult (for a record that needs escalation)
    plus its invoice row into the starting state for the graph.
    """
    return {
        "invoice_id": result.invoice_id,
        "invoice_number": invoice_row["invoice_number"],
        "invoice_amount": float(invoice_row["amount"]),
        "invoice_date": str(invoice_row["date"].date()) if hasattr(invoice_row["date"], "date") else str(invoice_row["date"]),
        "customer_name": invoice_row["customer_name"],
        "phase2_hop1_status": result.hop1_status,
        "phase2_hop2_status": result.hop2_status,
        "phase2_matched_payment_id": result.matched_payment_id,
        "phase2_matched_bank_txn_id": result.matched_bank_txn_id,
        "phase2_reasons": result.reasons,
        "route_target": None,
        "route_rationale": None,
        "search_attempts": [],
        "candidate_payments": [],
        "candidate_bank_txns": [],
        "final_status": None,
        "confidence": None,
        "justification": None,
        "exception_category": None,
    }


def run_agent_chain(
    escalated_results: list[ReconciliationResult],
    invoice_df,
    delay_between_records_seconds: float = 1.0,
    on_progress=None,
) -> list[ReconciliationState]:
    """
    Run every escalated Phase 2 record through the compiled graph.

    escalated_results should already be filtered to final_status in
    ("needs_review", "exception") -- records Phase 2 auto-resolved never
    need to reach here (that's the whole point of the two-phase design:
    keep the LLM off the majority of records).

    on_progress: optional callback, called as
        on_progress(index, total, invoice_id, final_state)
    after EACH record completes. Lets a caller (e.g. the Streamlit UI)
    show live per-record status instead of waiting for the whole batch.

    A small delay between records proactively spaces out Groq calls to
    avoid hitting requests-per-minute limits in the first place --
    nodes.py's reasoning_node also has reactive retry-with-backoff for
    when a rate limit is hit anyway.
    """
    import time

    app = build_graph()
    outputs = []
    total = len(escalated_results)

    for i, result in enumerate(escalated_results):
        invoice_row = invoice_df[invoice_df["invoice_id"] == result.invoice_id].iloc[0]
        initial_state = build_initial_state(result, invoice_row)
        final_state = app.invoke(initial_state)
        outputs.append(final_state)

        if on_progress is not None:
            on_progress(i, total, result.invoice_id, final_state)

        if delay_between_records_seconds > 0 and i < total - 1:
            time.sleep(delay_between_records_seconds)

    return outputs


def verify_single_record(result: ReconciliationResult, invoice_row) -> ReconciliationState:
    """
    Run exactly ONE record through the graph, on demand. Used by the
    "manually verify a specific invoice" UI feature -- lets a user pick
    any invoice and see the agent chain's full reasoning for it live,
    regardless of whether Phase 2 already resolved it.
    """
    app = build_graph()
    initial_state = build_initial_state(result, invoice_row)
    return app.invoke(initial_state)