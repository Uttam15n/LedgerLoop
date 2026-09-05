"""
Read-only, parameterized search tools -- the ONLY way the agent chain is
allowed to touch the database.

This is the security fix from our earlier design discussion, implemented:
    - a SEPARATE, read-only SQLite connection (opened with mode=ro), so
      even a fully compromised prompt cannot write, update, or delete
      anything, regardless of what SQL it might try to generate
    - NO open-ended SQL generation. The LLM never writes a query string.
      It only ever calls one of three functions below with plain
      arguments (table name, column name, value/range).
    - column names are checked against a whitelist (config.settings.SCHEMAS)
      before ever being placed into a query -- this is what stops an
      attacker from asking to search a column that doesn't exist, or one
      outside the reconciliation tables entirely (e.g. a users/secrets
      table elsewhere in the same database).
    - all VALUES are passed as SQL parameters ("?"), never string-interpolated
      -- this is what makes SQL injection structurally impossible here,
      not just discouraged.
    - every query is capped with a hard LIMIT, enforced in code, not left
      to the LLM's judgment.

Uses Python's built-in sqlite3 module directly (not SQLAlchemy) so this
connection is provably independent from the read/write engine used by
db/session.py and db/repository.py.
"""

import sqlite3
from datetime import datetime

from finance_controller.config.settings import DB_PATH, SCHEMAS

MAX_RESULTS = 20


class InvalidSearchError(ValueError):
    """Raised when a tool is called with a table/column outside the whitelist."""
    pass


def _get_readonly_connection() -> sqlite3.Connection:
    """
    Opens SQLite in read-only mode via URI, so a write attempt fails at the
    OS/driver level, not just by convention or credential scoping.
    """
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_table(table_key: str) -> str:
    if table_key not in SCHEMAS:
        raise InvalidSearchError(
            f"'{table_key}' is not a recognized table. Allowed: {list(SCHEMAS.keys())}"
        )
    return SCHEMAS[table_key]["table_name"]


def _validate_column(table_key: str, column: str) -> None:
    allowed = SCHEMAS[table_key]["required_columns"].keys()
    if column not in allowed:
        raise InvalidSearchError(
            f"'{column}' is not a searchable column on '{table_key}'. Allowed: {list(allowed)}"
        )


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def search_by_reference(table_key: str, column: str, value: str) -> list[dict]:
    """
    Find rows where `column` matches `value`, exactly or as a substring
    (catches truncated/reformatted references like a mangled UTR).

    Example: search_by_reference("bank_transaction", "utr_reference", "570220212633")
    """
    table_name = _validate_table(table_key)
    _validate_column(table_key, column)

    query = f"SELECT * FROM {table_name} WHERE {column} LIKE ? LIMIT ?"
    pattern = f"%{value}%"

    with _get_readonly_connection() as conn:
        rows = conn.execute(query, (pattern, MAX_RESULTS)).fetchall()
    return _rows_to_dicts(rows)


def search_by_amount_range(table_key: str, min_amount: float, max_amount: float) -> list[dict]:
    """
    Find rows where `amount` falls within [min_amount, max_amount].

    Example: search_by_amount_range("payment", 9400.0, 9550.0)
    """
    table_name = _validate_table(table_key)
    _validate_column(table_key, "amount")

    query = f"SELECT * FROM {table_name} WHERE amount BETWEEN ? AND ? LIMIT ?"

    with _get_readonly_connection() as conn:
        rows = conn.execute(query, (min_amount, max_amount, MAX_RESULTS)).fetchall()
    return _rows_to_dicts(rows)


def search_by_date_range(table_key: str, start_date: str, end_date: str) -> list[dict]:
    """
    Find rows where `date` falls within [start_date, end_date] (ISO format
    strings, e.g. "2026-08-01").

    Example: search_by_date_range("bank_transaction", "2026-08-05", "2026-08-15")
    """
    table_name = _validate_table(table_key)
    _validate_column(table_key, "date")

    
    datetime.fromisoformat(start_date)
    datetime.fromisoformat(end_date)

    query = f"SELECT * FROM {table_name} WHERE date BETWEEN ? AND ? LIMIT ?"

    with _get_readonly_connection() as conn:
        rows = conn.execute(query, (start_date, end_date, MAX_RESULTS)).fetchall()
    return _rows_to_dicts(rows)