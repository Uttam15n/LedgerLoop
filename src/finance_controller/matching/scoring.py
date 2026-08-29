"""
Pair scoring — the core deterministic matching logic, no LLM involved.

Given two records (e.g. one invoice + one payment, or one payment + one
bank_transaction), produce a single confidence score in [0, 1] built from
four independent signals: reference match, amount match, date proximity,
and fuzzy text similarity.

This function is deliberately GENERIC across both reconciliation hops
(invoice<->payment and payment<->bank_transaction) — it doesn't know or
care which table the records came from, only the four values it's given.
matcher.py (next file) is what maps table-specific column names onto
these generic parameters.
"""

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from finance_controller.config.settings import MATCH_TOLERANCE

# Signal weights — must sum to 1.0. Kept as constants here (not settings.py)
# because they're specific to HOW scoring combines signals, not a tolerance
# policy a controller would tune independently.
WEIGHT_REFERENCE = 0.40
WEIGHT_AMOUNT = 0.35
WEIGHT_DATE = 0.15
WEIGHT_TEXT = 0.10


@dataclass
class ScoreResult:
    total: float
    reference_score: float
    amount_score: float
    date_score: float
    text_score: float
    reasons: list[str]  # human-readable notes, feeds later exception reporting

    def summary(self) -> str:
        return (
            f"total={self.total:.2f} "
            f"(ref={self.reference_score:.2f}, amount={self.amount_score:.2f}, "
            f"date={self.date_score:.2f}, text={self.text_score:.2f})"
        )


def _score_reference(ref_a: str, ref_b: str) -> tuple[float, str | None]:
    if ref_a is None or ref_b is None or ref_a == "" or ref_b == "":
        return 0.0, "one or both references missing"
    if ref_a == ref_b:
        return 1.0, None
    # Partial credit for a "contains" relationship — this is exactly what
    # catches a truncated/reformatted UTR (e.g. bank kept only the last 8
    # digits, or added a prefix/dashes).
    a_clean = ref_a.replace("-", "").replace(" ", "")
    b_clean = ref_b.replace("-", "").replace(" ", "")
    if a_clean in b_clean or b_clean in a_clean:
        return 0.6, "reference matched partially (truncated/reformatted)"
    return 0.0, "references do not match"


def _score_amount(amount_a: float, amount_b: float) -> tuple[float, str | None]:
    diff = abs(amount_a - amount_b)
    if diff <= MATCH_TOLERANCE["amount_abs_tolerance"]:
        return 1.0, None
    pct_diff = diff / amount_a if amount_a else 1.0
    if pct_diff <= MATCH_TOLERANCE["amount_fee_tolerance_pct"]:
        return 0.7, f"amount differs by {pct_diff:.2%} (within fee tolerance)"
    return 0.0, f"amount differs by {diff:.2f} ({pct_diff:.2%}), outside tolerance"


def _score_date(date_a: datetime, date_b: datetime) -> tuple[float, str | None]:
    window = MATCH_TOLERANCE["date_window_days"]
    days_off = abs((date_a - date_b).days)
    if days_off > window:
        return 0.0, f"date differs by {days_off} days (outside {window}-day window)"
    score = max(0.0, 1 - days_off / window) if window > 0 else (1.0 if days_off == 0 else 0.0)
    reason = None if days_off == 0 else f"date differs by {days_off} day(s), within tolerance"
    return score, reason


def _score_text(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    return SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()


def score_pair(
    ref_a: str, ref_b: str,
    amount_a: float, amount_b: float,
    date_a: datetime, date_b: datetime,
    text_a: str = "", text_b: str = "",
) -> ScoreResult:
    """
    Score how likely two records represent the same real-world event.

    Parameters are generic on purpose — callers map their table's actual
    columns onto these (e.g. invoice.invoice_number -> ref_a,
    payment.invoice_reference -> ref_b).
    """
    reasons = []

    ref_score, ref_reason = _score_reference(ref_a, ref_b)
    if ref_reason:
        reasons.append(ref_reason)

    amount_score, amount_reason = _score_amount(amount_a, amount_b)
    if amount_reason:
        reasons.append(amount_reason)

    date_score, date_reason = _score_date(date_a, date_b)
    if date_reason:
        reasons.append(date_reason)

    text_score = _score_text(text_a, text_b)

    # If neither side supplied text, the text signal is unavailable for this
    # hop (e.g. invoice<->payment has no comparable free-text field) -- not
    # the same thing as text being present but dissimilar. Redistribute its
    # weight across the other three signals instead of wasting it, so a
    # perfect ref+amount+date match can still reach 1.0 rather than being
    # capped at (1 - WEIGHT_TEXT).
    text_available = bool(text_a) and bool(text_b)
    if text_available:
        w_ref, w_amount, w_date, w_text = WEIGHT_REFERENCE, WEIGHT_AMOUNT, WEIGHT_DATE, WEIGHT_TEXT
    else:
        remaining = WEIGHT_REFERENCE + WEIGHT_AMOUNT + WEIGHT_DATE
        scale = 1.0 / remaining
        w_ref = WEIGHT_REFERENCE * scale
        w_amount = WEIGHT_AMOUNT * scale
        w_date = WEIGHT_DATE * scale
        w_text = 0.0

    total = (
        w_ref * ref_score
        + w_amount * amount_score
        + w_date * date_score
        + w_text * text_score
    )

    return ScoreResult(
        total=total,
        reference_score=ref_score,
        amount_score=amount_score,
        date_score=date_score,
        text_score=text_score,
        reasons=reasons,
    )