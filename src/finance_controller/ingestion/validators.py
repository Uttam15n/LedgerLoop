"""
Schema validation — the gate every DataFrame must pass through before
db.repository.load_dataframe() is allowed to write it to SQLite.

Design choice: validation NEVER silently drops or repairs rows. It only
reports problems. This matters specifically for finance data — a validator
that quietly "fixes" a bad amount or drops a malformed row would corrupt
your match rate without anyone knowing. Every issue found here is surfaced
to the user (via Streamlit) and logged, and the human decides what to do.

Works generically off config.settings.SCHEMAS, so the same functions
validate invoice, payment, AND bank_transaction data — no per-table
special-casing.
"""

from dataclasses import dataclass, field

import pandas as pd

from finance_controller.config.settings import SCHEMAS

# Maps the schema's abstract type names to a check function.
_TYPE_CHECKERS = {
    "string": lambda s: s.astype("string").notna() | s.isna(),  # always true; real check is presence
    "float": lambda s: pd.to_numeric(s, errors="coerce").notna(),
    "datetime": lambda s: pd.to_datetime(s, errors="coerce").notna(),
}


@dataclass
class ValidationResult:
    table_key: str
    is_valid: bool
    row_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        return (
            f"[{status}] {self.table_key}: {self.row_count} rows, "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        )


def validate_dataframe(table_key: str, df: pd.DataFrame) -> ValidationResult:
    """
    Validate a DataFrame against the schema registered for table_key
    in config.settings.SCHEMAS.

    Checks performed:
      1. All required columns are present (ERROR if missing)
      2. No unexpected empty DataFrame (ERROR if 0 rows)
      3. Each column's values are coercible to its declared type (ERROR
         if a column fails entirely; WARNING if only some rows fail,
         since a nullable field like invoice_reference is allowed to be
         genuinely blank)
      4. Primary key column has no duplicate values (ERROR)
    """
    if table_key not in SCHEMAS:
        raise ValueError(f"Unknown table_key '{table_key}'. Expected one of {list(SCHEMAS.keys())}")

    schema = SCHEMAS[table_key]
    required_columns = schema["required_columns"]
    primary_key = schema["primary_key"]

    errors: list[str] = []
    warnings: list[str] = []

    if df.empty:
        errors.append("DataFrame has 0 rows.")
        return ValidationResult(table_key, False, 0, errors, warnings)

    # 1. required columns present
    missing_cols = [c for c in required_columns if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required column(s): {missing_cols}")
        # Can't safely check types on columns that don't exist — stop here.
        return ValidationResult(table_key, False, len(df), errors, warnings)

    # 2. unexpected extra columns -> warning only, never blocks a load
    extra_cols = [c for c in df.columns if c not in required_columns]
    if extra_cols:
        warnings.append(f"Unexpected column(s) present, will be ignored downstream: {extra_cols}")

    # 3. per-column type coercibility
    for col, declared_type in required_columns.items():
        checker = _TYPE_CHECKERS.get(declared_type)
        if checker is None:
            continue  # unknown declared type, skip rather than crash

        if declared_type == "string":
            null_count = df[col].isna().sum()
            if col == primary_key and null_count > 0:
                errors.append(f"Column '{col}' (primary key) has {null_count} null value(s).")
            elif null_count > 0:
                warnings.append(f"Column '{col}' has {null_count} null value(s).")
            continue

        valid_mask = checker(df[col])
        n_invalid = (~valid_mask).sum()
        if n_invalid == 0:
            continue

        pct_invalid = n_invalid / len(df)
        message = (
            f"Column '{col}' (expected {declared_type}) has {n_invalid}/{len(df)} "
            f"row(s) that don't coerce cleanly."
        )
        if pct_invalid >= 0.5:
            errors.append(message)
        else:
            warnings.append(message)

    # 4. primary key uniqueness
    if primary_key in df.columns:
        dup_count = df[primary_key].duplicated().sum()
        if dup_count > 0:
            errors.append(f"Primary key '{primary_key}' has {dup_count} duplicate value(s).")

    is_valid = len(errors) == 0
    return ValidationResult(table_key, is_valid, len(df), errors, warnings)


def coerce_dataframe(table_key: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Only call this AFTER validate_dataframe() reports is_valid=True.

    Converts column dtypes (string dates -> real datetime, numeric strings
    -> float) so what gets written to SQLite has consistent, query-able
    types. This does not fix data problems — it only formats already-valid
    data correctly.
    """
    schema = SCHEMAS[table_key]
    df = df.copy()

    for col, declared_type in schema["required_columns"].items():
        if col not in df.columns:
            continue
        if declared_type == "float":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif declared_type == "datetime":
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif declared_type == "string":
            df[col] = df[col].astype("string")

    return df