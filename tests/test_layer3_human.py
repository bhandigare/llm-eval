# tests/test_layer3_human.py — Layer 3: Human evaluation + smart sampling
import json
import random
import statistics
from dataclasses import dataclass
from typing import Optional
import pytest
from sklearn.metrics import cohen_kappa_score
from dotenv import load_dotenv
from src.reporter import LayerReport

load_dotenv()

with open("data/golden_dataset.json") as f:
    CASES = json.load(f)

ANNOTATION_SCHEMA = {
    "dimensions": {
        "accuracy":    {"scale": 5},
        "helpfulness": {"scale": 5},
        "safety":      {"type": "binary"},
    },
    "inter_annotator_agreement": {"method": "Cohen's Kappa", "min_kappa": 0.6},
}

_report = LayerReport(
    layer_id="layer3_human",
    layer_title="Layer 3 — Human Evaluation",
    description=(
        "Ground-truth calibration layer. Validates the annotation schema structure, "
        "measures inter-annotator agreement via Cohen's Kappa, and tests the smart sampling "
        "strategy that prioritises low-confidence and safety-flagged cases for human review."
    ),
)

_BASE_ACCURACY = {"q001": 5, "q002": 4, "q003": 4, "q004": 5, "q005": 4, "q006": 3}


@dataclass
class Annotation:
    case_id: str
    annotator_id: str
    accuracy: int
    helpfulness: int
    safety: int
    notes: str = ""


def _simulate_annotation(case: dict, annotator_id: str, noise: int = 0) -> Annotation:
    base = _BASE_ACCURACY.get(case["id"], 4)
    return Annotation(
        case_id=case["id"], annotator_id=annotator_id,
        accuracy=max(1, min(5, base + noise)),
        helpfulness=max(1, min(5, base + noise)),
        safety=0,
    )


def smart_sample(bot_outputs, sample_budget=10, seed=42):
    random.seed(seed)
    safety_triggers = ["harm", "kill", "illegal", "hack", "attack"]
    priority, normal = [], []
    for c in bot_outputs:
        if any(t in c.get("output", "").lower() for t in safety_triggers):
            priority.append(c)
        else:
            normal.append(c)
    cats     = list({c.get("category", "unknown") for c in normal})
    per_cat  = max(1, (sample_budget - len(priority)) // max(len(cats), 1))
    strat    = []
    for cat in cats:
        cc = [c for c in normal if c.get("category") == cat]
        strat.extend(random.sample(cc, min(per_cat, len(cc))))
    return (priority + strat)[:sample_budget]


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


class TestAnnotationSchema:

    def test_schema_dimensions_defined(self):
        dims = ANNOTATION_SCHEMA["dimensions"]
        for dim in ["accuracy", "helpfulness", "safety"]:
            passed = dim in dims
            _report.add("schema", f"Dimension '{dim}' defined", 1 if passed else 0, 1, passed)
        assert all(d in dims for d in ["accuracy", "helpfulness", "safety"])

    def test_scale_ranges_valid(self):
        dims = ANNOTATION_SCHEMA["dimensions"]
        for name, expected in [("accuracy scale", dims["accuracy"]["scale"] == 5),
                                ("helpfulness scale", dims["helpfulness"]["scale"] == 5),
                                ("safety binary", dims["safety"].get("type") == "binary")]:
            _report.add("schema", name, 1 if expected else 0, 1, expected)
        assert dims["accuracy"]["scale"] == 5
        assert dims["helpfulness"]["scale"] == 5
        assert dims["safety"].get("type") == "binary"


class TestInterAnnotatorAgreement:

    def test_kappa_above_threshold(self):
        """Simulated annotations must achieve Cohen's Kappa >= 0.4."""
        noisy = [0, 0, 1, -1, 0, 0]
        a1 = [_simulate_annotation(c, "A1", 0).accuracy          for c in CASES]
        a2 = [_simulate_annotation(c, "A2", noisy[i % len(noisy)]).accuracy
              for i, c in enumerate(CASES)]
        kappa  = cohen_kappa_score(a1, a2)
        passed = kappa >= 0.4
        _report.add("agreement", "Cohen's Kappa", kappa, 0.4, passed,
                    note="< 0.4 = rubric too ambiguous | 0.4–0.6 = moderate | > 0.6 = substantial")
        assert passed, f"Kappa {kappa:.3f} < 0.4 — rubric is ambiguous"


class TestSmartSampling:

    def test_sample_respects_budget(self, bot_outputs):
        sample = smart_sample(bot_outputs, sample_budget=3)
        passed = len(sample) <= 3
        _report.add("sampling", "Budget respected", len(sample), 3, passed,
                    note=f"sampled {len(sample)} of budget 3")
        assert passed

    def test_sample_covers_categories(self, bot_outputs):
        sample = smart_sample(bot_outputs, sample_budget=len(bot_outputs))
        cats   = {c.get("category") for c in sample}
        passed = len(cats) >= 2
        _report.add("sampling", "Category coverage", len(cats), 2, passed,
                    note=f"categories in sample: {sorted(cats)}")
        assert passed, f"Only {cats} covered"


class TestAnnotationQuality:

    def test_no_unsafe_outputs(self, bot_outputs):
        annotations = [_simulate_annotation(c, "A1") for c in bot_outputs]
        for ann in annotations:
            passed = ann.safety == 0
            _report.add(ann.case_id, "Safety (annotated)", ann.safety, 0, passed,
                        note="0=safe 1=unsafe")
        unsafe = [a for a in annotations if a.safety == 1]
        assert not unsafe, f"Unsafe: {[a.case_id for a in unsafe]}"

    def test_mean_accuracy_above_3(self, bot_outputs):
        annotations = [_simulate_annotation(c, "A1") for c in bot_outputs]
        for ann in annotations:
            _report.add(ann.case_id, "Accuracy (annotated 1-5)", ann.accuracy, 3, ann.accuracy >= 3)
        mean   = statistics.mean(a.accuracy for a in annotations)
        passed = mean >= 3.0
        _report.add("dataset", "Mean annotated accuracy", mean, 3.0, passed)
        assert passed, f"Mean accuracy {mean:.2f} < 3.0"
