"""
Central configuration for the AI Finance Controller.

Every later phase (ingestion, deterministic matcher, agents, reporting)
imports from here instead of hardcoding column names, tolerances, or paths.
This means a controller can change a matching tolerance without touching
a single line of pipeline logic.
"""

from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment variables from .env FIRST, before anything else.
# settings.py is imported by nearly every other module, so this guarantees
# GROQ_API_KEY (and anything else in .env) is available process-wide,
# regardless of which terminal/IDE/shell actually launched the script --
# this is more reliable than depending on a shell's env var propagation.
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# PROJECT_ROOT resolves to finance_controller/ regardless of where a script
# importing this file is run from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"

DB_PATH = DATA_PROCESSED_DIR / "staging.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

RUN_LOG_PATH = LOGS_DIR / "run_log.jsonl"

# Create these directories on import so nothing downstream has to remember to.
for _dir in (DATA_RAW_DIR, DATA_PROCESSED_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Source schemas — one entry per real-world data source.
# ---------------------------------------------------------------------------
# "required_columns" is what the ingestion validator checks BEFORE anything
# is written to the database. Adding a 4th source later means adding one
# entry here — no other file needs to change to support it.

INVOICE_SCHEMA = {
    "table_name": "invoice",
    "primary_key": "invoice_id",
    "required_columns": {
        "invoice_id": "string",
        "invoice_number": "string",
        "date": "datetime",
        "due_date": "datetime",
        "amount": "float",
        "currency": "string",
        "customer_name": "string",
        "status": "string",       # e.g. "open", "paid", "overdue"
    },
}

PAYMENT_SCHEMA = {
    "table_name": "payment",
    "primary_key": "payment_id",
    "required_columns": {
        "payment_id": "string",
        "utr": "string",              # UPI transaction reference
        "date": "datetime",
        "amount": "float",
        "payer_vpa": "string",        # UPI virtual payment address
        "invoice_reference": "string",  # should match invoice.invoice_number
    },
}

BANK_TRANSACTION_SCHEMA = {
    "table_name": "bank_transaction",
    "primary_key": "bank_txn_id",
    "required_columns": {
        "bank_txn_id": "string",
        "date": "datetime",
        "amount": "float",
        "currency": "string",
        "utr_reference": "string",    # should match payment.utr, often truncated/reformatted
        "description": "string",
    },
}

SCHEMAS = {
    "invoice": INVOICE_SCHEMA,
    "payment": PAYMENT_SCHEMA,
    "bank_transaction": BANK_TRANSACTION_SCHEMA,
}

# ---------------------------------------------------------------------------
# Reconciliation chain
# ---------------------------------------------------------------------------
# The order records should link in: invoice -> payment -> bank_transaction.
# The deterministic matcher and router agent both read this instead of
# having the chain order hardcoded in multiple places.
RECONCILIATION_CHAIN = ["invoice", "payment", "bank_transaction"]

# ---------------------------------------------------------------------------
# Matching tolerance policy (used starting Phase 2)
# ---------------------------------------------------------------------------
MATCH_TOLERANCE = {
    "amount_abs_tolerance": 0.02,       # absolute currency units (rounding)
    "amount_fee_tolerance_pct": 0.02,   # 2% - covers UPI/bank fee deltas
    "date_window_days": 3,              # settlement lag tolerance
}

CONFIDENCE_THRESHOLDS = {
    "auto_approve": 0.90,
    "human_review_floor": 0.60,
    # below human_review_floor -> exception
}

# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------
SYNTHETIC_INVOICE_COUNT = 55          # >50 per project requirement
SYNTHETIC_RANDOM_SEED = 42