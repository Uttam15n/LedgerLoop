"""
Central configuration for the AI Finance Controller.

Every later phase (ingestion, deterministic matcher, agents, reporting)
imports from here instead of hardcoding column names, tolerances, or paths.
This means a controller can change a matching tolerance without touching
a single line of pipeline logic.
"""

from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"

DB_PATH = DATA_PROCESSED_DIR / "staging.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

RUN_LOG_PATH = LOGS_DIR / "run_log.jsonl"


for _dir in (DATA_RAW_DIR, DATA_PROCESSED_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)



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
        "status": "string",      
    },
}

PAYMENT_SCHEMA = {
    "table_name": "payment",
    "primary_key": "payment_id",
    "required_columns": {
        "payment_id": "string",
        "utr": "string",              
        "date": "datetime",
        "amount": "float",
        "payer_vpa": "string",        
        "invoice_reference": "string",  
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
        "utr_reference": "string",    
        "description": "string",
    },
}

SCHEMAS = {
    "invoice": INVOICE_SCHEMA,
    "payment": PAYMENT_SCHEMA,
    "bank_transaction": BANK_TRANSACTION_SCHEMA,
}


RECONCILIATION_CHAIN = ["invoice", "payment", "bank_transaction"]


MATCH_TOLERANCE = {
    "amount_abs_tolerance": 0.02,       
    "amount_fee_tolerance_pct": 0.02,   
    "date_window_days": 3,              
}

CONFIDENCE_THRESHOLDS = {
    "auto_approve": 0.90,
    "human_review_floor": 0.60,
    
}


SYNTHETIC_INVOICE_COUNT = 55          
SYNTHETIC_RANDOM_SEED = 42