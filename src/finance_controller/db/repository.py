"""
Repository layer — typed read/write functions for the three source tables.

Why this file exists: without it, every part of the app (ingestion,
matcher, agents, Streamlit UI) would each write their own SQL or ORM
queries, and a schema change would mean hunting through the whole
codebase. Instead, every DB interaction goes through one of these
functions. Change how a table is written/read once, here, and every
caller benefits.

No LangGraph/LangChain here either — this is plain SQLAlchemy + pandas.
"""

from contextlib import contextmanager

import pandas as pd
from sqlalchemy.orm import Session

from finance_controller.db.session import SessionLocal, engine
from finance_controller.db.models import TABLE_MODELS


@contextmanager
def session_scope():
    """
    Context manager that hands you a session and guarantees it's closed,
    committing on success and rolling back on any exception.

    Usage:
        with session_scope() as session:
            session.add(some_object)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_dataframe(table_key: str, df: pd.DataFrame, replace: bool = True) -> int:
    """
    Bulk-load a validated DataFrame into its corresponding table.

    Parameters
    ----------
    table_key : one of "invoice", "payment", "bank_transaction"
                (matches the keys in config.settings.SCHEMAS / db.models.TABLE_MODELS)
    df        : a DataFrame that has already passed schema validation
    replace   : if True, wipes the table before loading (useful for re-running
                the same synthetic batch during development). If False, appends.

    Returns
    -------
    Number of rows written.
    """
    if table_key not in TABLE_MODELS:
        raise ValueError(
            f"Unknown table_key '{table_key}'. Expected one of {list(TABLE_MODELS.keys())}"
        )

    model = TABLE_MODELS[table_key]
    table_name = model.__tablename__

    if_exists_mode = "replace" if replace else "append"
    df.to_sql(table_name, con=engine, if_exists=if_exists_mode, index=False)

    return len(df)


def get_all(table_key: str) -> pd.DataFrame:
    """
    Read an entire table back as a DataFrame.

    This is what Phase 2's deterministic matcher will call for its ONE
    bulk read per table (see our earlier discussion — no per-record
    queries at this stage).
    """
    if table_key not in TABLE_MODELS:
        raise ValueError(
            f"Unknown table_key '{table_key}'. Expected one of {list(TABLE_MODELS.keys())}"
        )

    table_name = TABLE_MODELS[table_key].__tablename__
    return pd.read_sql(f"SELECT * FROM {table_name}", con=engine)


def get_row_count(table_key: str) -> int:
    """Cheap count without pulling the full table — used for UI summaries."""
    if table_key not in TABLE_MODELS:
        raise ValueError(
            f"Unknown table_key '{table_key}'. Expected one of {list(TABLE_MODELS.keys())}"
        )

    table_name = TABLE_MODELS[table_key].__tablename__
    with engine.connect() as conn:
        result = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}")
        return result.scalar_one()


def get_all_counts() -> dict[str, int]:
    """Row counts for every table at once — used by the Streamlit summary panel."""
    return {key: get_row_count(key) for key in TABLE_MODELS}


def clear_all_tables() -> dict[str, int]:
    """
    Delete every row from every table (keeps the schema, doesn't drop
    tables). Used by the UI's "Reset database" action so a fresh
    ingestion/reconciliation cycle can be tested without manually
    touching the SQLite file.

    Returns the row counts that were deleted, per table.
    """
    deleted = {}
    with engine.connect() as conn:
        for table_key, model in TABLE_MODELS.items():
            table_name = model.__tablename__
            before = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}").scalar_one()
            conn.exec_driver_sql(f"DELETE FROM {table_name}")
            deleted[table_key] = before
        conn.commit()
    return deleted