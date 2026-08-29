"""
Matcher — candidate generation + one-to-one assignment for a single
reconciliation hop (e.g. invoice<->payment, or payment<->bank_transaction).

This is deliberately generic: it doesn't know about invoices or payments
specifically, only about a "source" table and a "target" table connected
by a column mapping. That's what lets the SAME function run both hops of
the reconciliation chain without duplicated logic.

Three steps, matching what we discussed in the architecture:
  1. Candidate generation  — narrow target rows to a plausible date window
  2. Scoring                — score every (source, candidate) pair
  3. Global assignment      — greedy, highest-score-first, one-to-one,
                               so two sources can never silently claim the
                               same target (this is exactly what catches
                               the duplicate_candidate case correctly)
"""

from dataclasses import dataclass, field

import pandas as pd

from finance_controller.config.settings import MATCH_TOLERANCE, CONFIDENCE_THRESHOLDS
from finance_controller.matching.scoring import score_pair, ScoreResult

# If a source row's top two candidates score within this margin of each
# other, we flag it as a duplicate/ambiguous match regardless of what the
# top score alone would suggest -- picking one silently would be wrong.
DUPLICATE_SCORE_MARGIN = 0.05


@dataclass
class CandidateScore:
    target_id: str
    score: ScoreResult


@dataclass
class MatchOutcome:
    source_id: str
    status: str                     # "auto_matched" | "human_review" | "no_match" | "duplicate_candidate"
    matched_target_id: str | None
    best_score: ScoreResult | None
    all_candidates: list[CandidateScore] = field(default_factory=list)

    def summary(self) -> str:
        score_str = f"{self.best_score.total:.2f}" if self.best_score else "n/a"
        return f"[{self.status}] {self.source_id} -> {self.matched_target_id} (score={score_str})"


@dataclass
class ColumnMapping:
    """Maps a table-pair's actual column names onto scoring's generic slots."""
    source_id_col: str
    target_id_col: str
    source_ref_col: str
    target_ref_col: str
    source_amount_col: str
    target_amount_col: str
    source_date_col: str
    target_date_col: str
    source_text_col: str | None = None
    target_text_col: str | None = None


def _generate_candidates(source_row: pd.Series, target_df: pd.DataFrame, mapping: ColumnMapping) -> pd.DataFrame:
    """Narrow target_df to rows within the date tolerance window of source_row."""
    window = MATCH_TOLERANCE["date_window_days"]
    source_date = source_row[mapping.source_date_col]
    date_diff = (target_df[mapping.target_date_col] - source_date).abs().dt.days
    return target_df[date_diff <= window]


def match_one_to_one(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    mapping: ColumnMapping,
) -> list[MatchOutcome]:
    """
    Run the full candidate-generation -> scoring -> assignment pipeline
    for one reconciliation hop.
    """
    thresholds = CONFIDENCE_THRESHOLDS

    # --- Step 1 + 2: candidates + scores, per source row ---
    per_source_candidates: dict[str, list[CandidateScore]] = {}

    for _, source_row in source_df.iterrows():
        source_id = source_row[mapping.source_id_col]
        candidates = _generate_candidates(source_row, target_df, mapping)

        scored = []
        for _, target_row in candidates.iterrows():
            text_a = source_row.get(mapping.source_text_col, "") if mapping.source_text_col else ""
            text_b = target_row.get(mapping.target_text_col, "") if mapping.target_text_col else ""

            result = score_pair(
                ref_a=source_row[mapping.source_ref_col],
                ref_b=target_row[mapping.target_ref_col],
                amount_a=source_row[mapping.source_amount_col],
                amount_b=target_row[mapping.target_amount_col],
                date_a=source_row[mapping.source_date_col],
                date_b=target_row[mapping.target_date_col],
                text_a=str(text_a) if pd.notna(text_a) else "",
                text_b=str(text_b) if pd.notna(text_b) else "",
            )
            scored.append(CandidateScore(target_id=target_row[mapping.target_id_col], score=result))

        scored.sort(key=lambda c: c.score.total, reverse=True)
        per_source_candidates[source_id] = scored

    # --- Step 3: global greedy one-to-one assignment ---
    # Build every (source, candidate) pair with score > 0, sort globally by
    # score descending, then walk down claiming source+target once each.
    # This is what prevents two sources both grabbing the same top target
    # independently -- assignment is coordinated across the WHOLE batch.
    all_pairs = []
    for source_id, candidates in per_source_candidates.items():
        for c in candidates:
            if c.score.total > 0:
                all_pairs.append((source_id, c.target_id, c.score))
    all_pairs.sort(key=lambda p: p[2].total, reverse=True)

    claimed_sources: set[str] = set()
    claimed_targets: set[str] = set()
    assignment: dict[str, tuple[str, ScoreResult]] = {}

    for source_id, target_id, score in all_pairs:
        if source_id in claimed_sources or target_id in claimed_targets:
            continue
        assignment[source_id] = (target_id, score)
        claimed_sources.add(source_id)
        claimed_targets.add(target_id)

    # --- Classify every source row into a final outcome ---
    outcomes = []
    for source_id, candidates in per_source_candidates.items():
        assigned = assignment.get(source_id)

        # duplicate detection: top-2 candidates too close to call, even if
        # one of them ended up assigned -- a human should confirm this one.
        is_duplicate = (
            len(candidates) >= 2
            and candidates[0].score.total - candidates[1].score.total < DUPLICATE_SCORE_MARGIN
            and candidates[0].score.total >= thresholds["human_review_floor"]
        )

        if not candidates:
            outcomes.append(MatchOutcome(source_id, "no_match", None, None, []))
            continue

        if is_duplicate:
            outcomes.append(MatchOutcome(
                source_id, "duplicate_candidate",
                assigned[0] if assigned else None,
                assigned[1] if assigned else candidates[0].score,
                candidates,
            ))
            continue

        if assigned is None:
            # had candidates, but lost every one to a higher-scoring competitor
            outcomes.append(MatchOutcome(source_id, "no_match", None, candidates[0].score, candidates))
            continue

        target_id, score = assigned
        if score.total >= thresholds["auto_approve"]:
            status = "auto_matched"
        elif score.total >= thresholds["human_review_floor"]:
            status = "human_review"
        else:
            status = "no_match"

        outcomes.append(MatchOutcome(source_id, status, target_id, score, candidates))

    return outcomes