"""
Structured, append-only audit logging.

Finance-ops tooling needs an audit trail more than pretty console output —
who/what ran, when, on what data. Every event is written as one JSON line
to logs/run_log.jsonl so later phases (and a human auditor) can reconstruct
exactly what happened to a given batch, including every validation issue
and every DB load.
"""

import json
import uuid
from datetime import datetime, timezone

from finance_controller.config.settings import RUN_LOG_PATH


def new_run_id() -> str:
    """One run_id per ingestion session, so all events can be grouped later."""
    return f"run_{uuid.uuid4().hex[:12]}"


def log_event(run_id: str, stage: str, event: str, **details) -> None:
    """
    Append one structured event to the run log.

    Parameters
    ----------
    run_id : the session this event belongs to (from new_run_id())
    stage  : pipeline stage, e.g. "ingestion", "validation", "db_load"
    event  : short event name, e.g. "file_uploaded", "schema_error"
    details: any additional structured fields (row counts, error text, etc.)
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "stage": stage,
        "event": event,
        **details,
    }
    with open(RUN_LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def read_log(run_id: str | None = None) -> list[dict]:
    """Read back log entries, optionally filtered to a single run_id."""
    if not RUN_LOG_PATH.exists():
        return []
    entries = []
    with open(RUN_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if run_id is None or record.get("run_id") == run_id:
                entries.append(record)
    return entries