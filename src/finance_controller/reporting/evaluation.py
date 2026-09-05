"""
Evaluation harness -- scores the final report against the synthetic data's
known ground truth. This is the "measured accuracy" piece: build_report()
tells you what the system DECIDED, this module tells you how often that
decision was actually RIGHT.

The ground_truth DataFrame comes from ingestion.synthetic.generate_synthetic_batch()
and is deliberately kept separate from everything the matcher/agents ever
see -- it's the answer key, not an input.

Ground truth's "expected_outcome" values (set per case type at generation
time) are mapped onto our three report buckets so they're directly
comparable:

    auto_match                  -> auto_approved
    human_review                -> human_review
    duplicate_candidate         -> human_review
    exception_missing_payment   -> exception
    exception_missing_bank_hit  -> exception
"""

from dataclasses import dataclass, field

import pandas as pd

EXPECTED_OUTCOME_TO_BUCKET = {
    "auto_match": "auto_approved",
    "human_review": "human_review",
    "duplicate_candidate": "human_review",
    "exception_missing_payment": "exception",
    "exception_missing_bank_hit": "exception",
}

BUCKETS = ["auto_approved", "human_review", "exception"]


@dataclass
class EvaluationResult:
    overall_accuracy: float
    total_records: int
    confusion_matrix: pd.DataFrame            
    per_bucket_precision: dict                
    per_bucket_recall: dict                   
    per_case_type_accuracy: pd.DataFrame       
    mismatches: pd.DataFrame                    

    def print_summary(self) -> None:
        print("=" * 60)
        print("EVALUATION AGAINST GROUND TRUTH")
        print("=" * 60)
        print(f"Overall accuracy: {self.overall_accuracy:.1%}  ({self.total_records} records)")
        print()
        print("Confusion matrix (rows = expected, columns = actual):")
        print(self.confusion_matrix)
        print()
        print("Per-bucket precision / recall:")
        for bucket in BUCKETS:
            p = self.per_bucket_precision.get(bucket, float("nan"))
            r = self.per_bucket_recall.get(bucket, float("nan"))
            print(f"  {bucket:15s}  precision={p:.1%}  recall={r:.1%}")
        print()
        print("Accuracy by synthetic case type:")
        print(self.per_case_type_accuracy)
        if not self.mismatches.empty:
            print()
            print(f"{len(self.mismatches)} mismatch(es):")
            print(self.mismatches[["invoice_id", "case_type", "expected_bucket", "actual_bucket"]])
        print("=" * 60)


def evaluate_against_ground_truth(
    report_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
) -> EvaluationResult:
    """
    report_df: report.to_dataframe() output -- must have invoice_id, bucket
    ground_truth_df: the "ground_truth" DataFrame from generate_synthetic_batch()
                      -- must have invoice_id, case_type, expected_outcome
    """
    merged = ground_truth_df.merge(
        report_df[["invoice_id", "bucket"]], on="invoice_id", how="inner",
    )
    merged["expected_bucket"] = merged["expected_outcome"].map(EXPECTED_OUTCOME_TO_BUCKET)
    merged = merged.rename(columns={"bucket": "actual_bucket"})

    total = len(merged)
    correct = (merged["expected_bucket"] == merged["actual_bucket"]).sum()
    overall_accuracy = correct / total if total else 0.0

    confusion = pd.crosstab(merged["expected_bucket"], merged["actual_bucket"])
    for b in BUCKETS:
        if b not in confusion.index:
            confusion.loc[b] = 0
        if b not in confusion.columns:
            confusion[b] = 0
    confusion = confusion.loc[BUCKETS, BUCKETS]

    precision, recall = {}, {}
    for bucket in BUCKETS:
        tp = ((merged["actual_bucket"] == bucket) & (merged["expected_bucket"] == bucket)).sum()
        fp = ((merged["actual_bucket"] == bucket) & (merged["expected_bucket"] != bucket)).sum()
        fn = ((merged["actual_bucket"] != bucket) & (merged["expected_bucket"] == bucket)).sum()
        precision[bucket] = tp / (tp + fp) if (tp + fp) else float("nan")
        recall[bucket] = tp / (tp + fn) if (tp + fn) else float("nan")

    per_case = (
        merged.assign(correct=merged["expected_bucket"] == merged["actual_bucket"])
        .groupby("case_type")
        .agg(accuracy=("correct", "mean"), n=("correct", "size"))
        .round(4)
    )

    mismatches = merged[merged["expected_bucket"] != merged["actual_bucket"]].copy()

    return EvaluationResult(
        overall_accuracy=round(overall_accuracy, 4),
        total_records=total,
        confusion_matrix=confusion,
        per_bucket_precision=precision,
        per_bucket_recall=recall,
        per_case_type_accuracy=per_case,
        mismatches=mismatches,
    )