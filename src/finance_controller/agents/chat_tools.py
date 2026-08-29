"""
LangChain @tool wrappers around agents/tools.py's read-only search functions,
for use by the chat assistant (bind_tools + tool-calling loop).

Deliberately thin: these just call straight through to the already
whitelisted, parameterized, security-tested functions in tools.py. No new
DB access logic here -- the chat assistant gets exactly the same
read-only, injection-safe search surface as the Phase 3 reasoning agent,
nothing more. The @tool decorator's docstring is what the LLM reads to
decide when/how to call each one, so these are written for the model's
benefit, not just documentation.
"""

from langchain_core.tools import tool

from finance_controller.agents.tools import (
    search_by_reference,
    search_by_amount_range,
    search_by_date_range,
)


@tool
def search_by_reference_tool(table_key: str, column: str, value: str) -> list[dict]:
    """
    Search a table for rows where a column matches a value, exactly or as
    a substring. table_key must be one of: "invoice", "payment",
    "bank_transaction". Use this to look up a specific invoice number
    (column="invoice_number" on "invoice", or column="invoice_reference"
    on "payment"), or a UTR (column="utr" on "payment", or
    column="utr_reference" on "bank_transaction").
    """
    return search_by_reference(table_key, column, value)


@tool
def search_by_amount_range_tool(table_key: str, min_amount: float, max_amount: float) -> list[dict]:
    """
    Search a table for rows where amount falls within [min_amount, max_amount].
    table_key must be one of: "invoice", "payment", "bank_transaction".
    Use this to find transactions near a known amount when you don't have
    an exact reference to search by.
    """
    return search_by_amount_range(table_key, min_amount, max_amount)


@tool
def search_by_date_range_tool(table_key: str, start_date: str, end_date: str) -> list[dict]:
    """
    Search a table for rows where date falls within [start_date, end_date]
    (ISO format strings, e.g. "2026-08-01"). table_key must be one of:
    "invoice", "payment", "bank_transaction".
    """
    return search_by_date_range(table_key, start_date, end_date)


CHAT_TOOLS = [search_by_reference_tool, search_by_amount_range_tool, search_by_date_range_tool]