"""
File loaders — turn an uploaded file (Streamlit's UploadedFile object) or
a plain filesystem path into a pandas DataFrame.

This is deliberately the ONLY file that touches file I/O for ingestion.
Everything after this point (validators.py, repository.py) works purely
with DataFrames and doesn't care whether the data originally came from
a Streamlit upload, a CSV on disk, or generate_synthetic_batch().

Supported formats: .csv, .xlsx
"""

from pathlib import Path
from typing import Union

import pandas as pd


FileLike = Union[str, Path, "object"]


class UnsupportedFileTypeError(ValueError):
    """Raised when a file's extension isn't one we know how to read."""
    pass


def _get_filename(file: FileLike) -> str:
    """Works for both plain paths and Streamlit's UploadedFile objects."""
    if isinstance(file, (str, Path)):
        return str(file)
    name = getattr(file, "name", None)
    if name is None:
        raise UnsupportedFileTypeError(
            "Could not determine filename from the given file object."
        )
    return name


def load_file_to_dataframe(file: FileLike) -> pd.DataFrame:
    """
    Read a .csv or .xlsx file into a DataFrame.

    Accepts:
      - a filesystem path (str or Path)
      - a Streamlit UploadedFile object (from st.file_uploader)

    Raises
    ------
    UnsupportedFileTypeError if the extension isn't .csv or .xlsx
    """
    filename = _get_filename(file)
    suffix = Path(filename).suffix.lower()

    try:
        if suffix == ".csv":
            df = pd.read_csv(file)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(file)
        else:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{suffix}' for file '{filename}'. "
                "Expected .csv or .xlsx."
            )
    except UnsupportedFileTypeError:
        raise
    except Exception as e:
        
        raise ValueError(f"Failed to read '{filename}': {e}") from e

    return df


def load_raw_csvs(table_keys: list[str]) -> dict[str, pd.DataFrame]:
    """
    Convenience loader for the synthetic-data workflow: reads the CSVs
    that ingestion.synthetic.save_synthetic_batch_to_raw() wrote into
    data/raw/, keyed by table name (invoice, payment, bank_transaction).

    Kept separate from load_file_to_dataframe() because this one KNOWS
    the file naming convention ("{table_key}.csv") — a real upload from
    a user won't necessarily follow that convention.
    """
    from finance_controller.config.settings import DATA_RAW_DIR

    result = {}
    for key in table_keys:
        path = DATA_RAW_DIR / f"{key}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Expected raw file for '{key}' at {path}, but it doesn't exist. "
                "Run ingestion.synthetic.save_synthetic_batch_to_raw() first."
            )
        result[key] = load_file_to_dataframe(path)
    return result


class ExcelWorkbookError(ValueError):
    """Raised when a single-workbook upload's sheets don't match the expected tables."""
    pass


def load_excel_workbook(file: FileLike, expected_keys: list[str]) -> dict[str, pd.DataFrame]:
    """
    Read ONE .xlsx file containing multiple sheets -- one sheet per table
    (invoice, payment, bank_transaction) -- into a dict of DataFrames.

    This is the "upload a single Excel workbook" convenience path, as an
    alternative to uploading three separate files. Sheet names are matched
    to expected_keys case-insensitively and with spaces/dashes normalized
    to underscores, so "Bank Transaction", "bank-transaction", and
    "bank_transaction" all match the same expected key.

    Raises ExcelWorkbookError with a clear message (listing what sheets
    were found vs. expected) if the match isn't complete -- never silently
    guesses which sheet is which.
    """
    filename = _get_filename(file)
    suffix = Path(filename).suffix.lower()
    if suffix not in (".xlsx", ".xls"):
        raise UnsupportedFileTypeError(
            f"Expected a .xlsx workbook, got '{suffix}' for file '{filename}'."
        )

    try:
        sheets = pd.read_excel(file, sheet_name=None)  
    except Exception as e:
        raise ValueError(f"Failed to read workbook '{filename}': {e}") from e

    def _normalize(name: str) -> str:
        return name.strip().lower().replace(" ", "_").replace("-", "_")

    normalized_sheets = {_normalize(name): df for name, df in sheets.items()}

    result = {}
    missing = []
    for key in expected_keys:
        if key in normalized_sheets:
            result[key] = normalized_sheets[key]
        else:
            missing.append(key)

    if missing:
        raise ExcelWorkbookError(
            f"Workbook '{filename}' is missing sheet(s) for: {missing}. "
            f"Sheets found: {list(sheets.keys())}. "
            f"Expected sheet names (case-insensitive): {expected_keys}."
        )

    return result