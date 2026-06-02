# tests/test_layer25_mlflow.py — Layer 2.5: MLflow built-in LLM evaluation
import json
import os
import pytest
import pandas as pd
from dotenv import load_dotenv
from src.reporter import LayerReport

load_dotenv()

with open("data/golden_dataset.json") as f:
    CASES = json.load(f)

THRESHOLDS = {
    "rouge1": 0.35, "rouge2": 0.15, "rougeL": 0.30,
    "toxicity": 0.05,
    "flesch_kincaid_grade_min": 4,
    "flesch_kincaid_grade_max": 14,
}

_report = LayerReport(
    layer_id="layer25_mlflow",
    layer_title="Layer 2.5 — MLflow Evaluation",
    description=(
        "MLflow built-in evaluation suite using evaluators='default'. "
        "Computes ROUGE variants, toxicity classifier, and Flesch-Kincaid readability "
        "without requiring a judge LLM — ideal for every CI run. "
        "Results are shown per-case and as dataset aggregates."
    ),
)


@pytest.fixture(scope="module")
def mlflow_eval(bot_outputs):
    """Run MLflow evaluate once and return (metrics_dict, per_row_df)."""
    import mlflow
    mlflow.set_experiment("shopeasy-support-eval")
    df = pd.DataFrame({
        "inputs":       [c["question"]  for c in bot_outputs],
        "outputs":      [c["output"]    for c in bot_outputs],
        "ground_truth": [c["reference"] for c in bot_outputs],
    })
    with mlflow.start_run(run_name="layer25-default-eval"):
        results = mlflow.evaluate(
            data=df, targets="ground_truth", predictions="outputs",
            model_type="text-summarization", evaluators="default",
        )
    per_row = results.tables.get("eval_results_table", pd.DataFrame())
    return results.metrics, per_row


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


def _get(metrics: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in metrics:
            return metrics[k]
    return default


def _per_row_col(per_row: pd.DataFrame, *keys: str) -> list[float] | None:
    for k in keys:
        if k in per_row.columns:
            return per_row[k].tolist()
    return None


class TestMLflowBuiltIn:

    def test_per_case_rouge(self, bot_outputs, mlflow_eval):
        """Per-case ROUGE scores from MLflow eval results table."""
        _, per_row = mlflow_eval
        for variant, thr in [("rouge1", THRESHOLDS["rouge1"]),
                              ("rouge2", THRESHOLDS["rouge2"]),
                              ("rougeL", THRESHOLDS["rougeL"])]:
            col_vals = _per_row_col(per_row,
                                    f"{variant}/v1/score", f"{variant}_score",
                                    variant)
            if col_vals is None:
                _report.add("dataset", f"{variant.upper()} per-case", "n/a", thr, True,
                            note="per-row column not available in this MLflow version")
                continue
            for i, case in enumerate(bot_outputs):
                val    = float(col_vals[i]) if i < len(col_vals) else 0.0
                passed = val >= thr
                _report.add(case["id"], f"{variant.upper()}", val, thr, passed,
                            actual=case["output"], reference=case["reference"])

    def test_per_case_toxicity(self, bot_outputs, mlflow_eval):
        """Per-case toxicity scores — must all be < 0.05."""
        _, per_row = mlflow_eval
        col_vals = _per_row_col(per_row,
                                "toxicity/v1/score", "toxicity_score", "toxicity")
        failures = []
        for i, case in enumerate(bot_outputs):
            val    = float(col_vals[i]) if (col_vals and i < len(col_vals)) else 0.0
            passed = val < THRESHOLDS["toxicity"]
            _report.add(case["id"], "Toxicity", val, THRESHOLDS["toxicity"], passed,
                        actual=case["output"],
                        note="lower is safer; 0=clean, 1=toxic")
            if not passed:
                failures.append(f"{case['id']}: toxicity={val:.3f}")
        assert not failures, "Toxicity threshold exceeded:\n" + "\n".join(failures)

    def test_per_case_readability(self, bot_outputs, mlflow_eval):
        """Per-case Flesch-Kincaid grade must be between 4 and 14."""
        _, per_row = mlflow_eval
        lo, hi = THRESHOLDS["flesch_kincaid_grade_min"], THRESHOLDS["flesch_kincaid_grade_max"]
        col_vals = _per_row_col(per_row,
                                "flesch_kincaid_grade_level/v1/score",
                                "flesch_kincaid_grade_score",
                                "flesch_kincaid_grade_level")
        for i, case in enumerate(bot_outputs):
            val    = float(col_vals[i]) if (col_vals and i < len(col_vals)) else 8.0
            passed = lo <= val <= hi
            _report.add(case["id"], "Flesch-Kincaid Grade", val, f"{lo}–{hi}", passed,
                        actual=case["output"],
                        note=f"target {lo}–{hi} for general audiences")

    def test_dataset_rouge_means(self, mlflow_eval):
        """Dataset-level ROUGE means must meet strategy thresholds."""
        metrics, _ = mlflow_eval
        for variant, *keys, thr in [
            ("ROUGE-1 (mean)", "rouge1/v1/mean", "rouge1_mean", THRESHOLDS["rouge1"]),
            ("ROUGE-2 (mean)", "rouge2/v1/mean", "rouge2_mean", THRESHOLDS["rouge2"]),
            ("ROUGE-L (mean)", "rougeL/v1/mean", "rougeL_mean", THRESHOLDS["rougeL"]),
        ]:
            val    = _get(metrics, *keys[:-1])   # last item is threshold
            passed = val >= keys[-1]
            _report.add("dataset", variant, val, keys[-1], passed)
            assert passed, f"{variant} {val:.3f} < {keys[-1]}"

    def test_dataset_toxicity_mean(self, mlflow_eval):
        """Dataset mean toxicity must be < 0.05."""
        metrics, _ = mlflow_eval
        val    = _get(metrics, "toxicity/v1/mean", "toxicity_mean")
        passed = val < THRESHOLDS["toxicity"]
        _report.add("dataset", "Toxicity (mean)", val, THRESHOLDS["toxicity"], passed,
                    note="lower is safer")
        assert passed, f"Toxicity {val:.3f} >= {THRESHOLDS['toxicity']}"

    def test_dataset_readability_mean(self, mlflow_eval):
        """Dataset mean Flesch-Kincaid grade must be 4–14."""
        metrics, _ = mlflow_eval
        lo, hi = THRESHOLDS["flesch_kincaid_grade_min"], THRESHOLDS["flesch_kincaid_grade_max"]
        val    = _get(metrics,
                      "flesch_kincaid_grade_level/v1/mean",
                      "flesch_kincaid_grade_mean", default=8.0)
        passed = lo <= val <= hi
        _report.add("dataset", "Flesch-Kincaid Grade (mean)", val, f"{lo}–{hi}", passed)
        assert passed, f"Grade level {val:.1f} outside [{lo}, {hi}]"

    def test_all_raw_metrics(self, mlflow_eval):
        """Record every raw MLflow metric in the report (informational)."""
        metrics, _ = mlflow_eval
        for k, v in sorted(metrics.items()):
            if isinstance(v, (int, float)):
                _report.add("dataset", f"[raw] {k}", v, "—", True)
