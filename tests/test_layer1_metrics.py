# tests/test_layer1_metrics.py — Layer 1: Unit metric testing
# Metrics: BLEU · ROUGE-1/2/L · METEOR · BERTScore · Exact Match
import re
import statistics
import pytest
import nltk
import bert_score
from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU
from nltk.translate.meteor_score import meteor_score
from src.reporter import LayerReport

nltk.data.path.insert(0, "/Users/maheshbhandigare/nltk_data")

rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
bleu  = BLEU(effective_order=True)

THRESHOLDS = {
    "bleu_corpus":       20.0,
    "rouge1_mean":        0.40,
    "rouge2_mean":        0.15,
    "rougeL_mean":        0.30,
    "meteor_mean":        0.30,
    "bertscore_f1_mean":  0.82,
    "bertscore_f1_min":   0.70,
}

_report = LayerReport(
    layer_id="layer1_metrics",
    layer_title="Layer 1 — Unit Metric Testing",
    description=(
        "Fast deterministic metrics computed on every commit. "
        "Covers all six strategy-doc metrics: BLEU, ROUGE-1/2/L, METEOR, BERTScore, and Exact Match. "
        "Each metric is shown per-case and as a dataset-level aggregate."
    ),
)


def _norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _meteor(ref: str, hyp: str) -> float:
    return meteor_score(
        [nltk.word_tokenize(ref.lower())],
        nltk.word_tokenize(hyp.lower())
    )


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


# ── BERTScore (computed once, shared across tests) ─────────────────────────────

@pytest.fixture(scope="module")
def bs_scores(bot_outputs):
    cands = [c["output"]    for c in bot_outputs]
    refs  = [c["reference"] for c in bot_outputs]
    P, R, F1 = bert_score.score(cands=cands, refs=refs, lang="en", verbose=False)
    return P, R, F1


# ── ROUGE ──────────────────────────────────────────────────────────────────────

class TestROUGE:

    def test_rouge_per_case(self, bot_outputs):
        """Per-case ROUGE-1, ROUGE-2, ROUGE-L — each case must meet its dataset threshold."""
        failures = []
        for case in bot_outputs:
            s   = rouge.score(case["reference"], case["output"])
            thr = case.get("min_rouge_l", THRESHOLDS["rougeL_mean"])

            _report.add(case["id"], "ROUGE-1",
                        s["rouge1"].fmeasure, THRESHOLDS["rouge1_mean"],
                        s["rouge1"].fmeasure >= THRESHOLDS["rouge1_mean"],
                        actual=case["output"], reference=case["reference"])

            _report.add(case["id"], "ROUGE-2",
                        s["rouge2"].fmeasure, THRESHOLDS["rouge2_mean"],
                        s["rouge2"].fmeasure >= THRESHOLDS["rouge2_mean"],
                        actual=case["output"], reference=case["reference"])

            passed_l = s["rougeL"].fmeasure >= thr
            _report.add(case["id"], "ROUGE-L",
                        s["rougeL"].fmeasure, thr, passed_l,
                        actual=case["output"], reference=case["reference"],
                        note=f"per-case threshold={thr}")
            if not passed_l:
                failures.append(f"{case['id']}: ROUGE-L={s['rougeL'].fmeasure:.3f} < {thr}")

        assert not failures, "ROUGE-L per-case failures:\n" + "\n".join(failures)

    def test_mean_rouge_thresholds(self, bot_outputs):
        """Dataset-level mean must meet strategy thresholds."""
        r1 = [rouge.score(c["reference"], c["output"])["rouge1"].fmeasure for c in bot_outputs]
        r2 = [rouge.score(c["reference"], c["output"])["rouge2"].fmeasure for c in bot_outputs]
        rl = [rouge.score(c["reference"], c["output"])["rougeL"].fmeasure for c in bot_outputs]

        for name, scores, thr in [
            ("ROUGE-1 (mean)", r1, THRESHOLDS["rouge1_mean"]),
            ("ROUGE-2 (mean)", r2, THRESHOLDS["rouge2_mean"]),
            ("ROUGE-L (mean)", rl, THRESHOLDS["rougeL_mean"]),
        ]:
            mean   = statistics.mean(scores)
            passed = mean >= thr
            _report.add("dataset", name, mean, thr, passed,
                        note=f"per-case: {[f'{s:.2f}' for s in scores]}")
            assert passed, f"{name} {mean:.3f} below {thr}"


# ── BLEU ───────────────────────────────────────────────────────────────────────

class TestBLEU:

    def test_per_case_bleu(self, bot_outputs):
        """Sentence BLEU per case — must be >= 2.0 (catches completely off-topic responses)."""
        failures = []
        for case in bot_outputs:
            result = bleu.sentence_score(case["output"], [case["reference"]])
            passed = result.score >= 2.0
            _report.add(case["id"], "BLEU (sentence)", result.score, 2.0, passed,
                        actual=case["output"], reference=case["reference"])
            if not passed:
                failures.append(f"{case['id']}: BLEU={result.score:.1f}")
        assert not failures, "Per-case BLEU < 2.0:\n" + "\n".join(failures)

    def test_corpus_bleu(self, bot_outputs):
        """Corpus BLEU >= 20."""
        hyps   = [c["output"]     for c in bot_outputs]
        refs   = [[c["reference"]] for c in bot_outputs]
        result = bleu.corpus_score(hyps, [[r[0] for r in refs]])
        passed = result.score >= THRESHOLDS["bleu_corpus"]
        _report.add("dataset", "BLEU (corpus)", result.score, THRESHOLDS["bleu_corpus"], passed,
                    note=str(result))
        assert passed, f"Corpus BLEU {result.score:.1f} below {THRESHOLDS['bleu_corpus']}"


# ── METEOR ─────────────────────────────────────────────────────────────────────

class TestMETEOR:

    def test_per_case_meteor(self, bot_outputs):
        """Per-case METEOR — no case may score 0.0."""
        failures = []
        for case in bot_outputs:
            score  = _meteor(case["reference"], case["output"])
            passed = score > 0.0
            _report.add(case["id"], "METEOR", score, THRESHOLDS["meteor_mean"], passed,
                        actual=case["output"], reference=case["reference"],
                        note="synonym-aware metric; threshold shown is mean gate")
            if not passed:
                failures.append(f"{case['id']}: METEOR=0.0")
        assert not failures, "Zero-METEOR cases:\n" + "\n".join(failures)

    def test_mean_meteor(self, bot_outputs):
        """Mean METEOR >= 0.30."""
        scores = [_meteor(c["reference"], c["output"]) for c in bot_outputs]
        mean   = statistics.mean(scores)
        passed = mean >= THRESHOLDS["meteor_mean"]
        _report.add("dataset", "METEOR (mean)", mean, THRESHOLDS["meteor_mean"], passed,
                    note=f"per-case: {[f'{s:.2f}' for s in scores]}")
        assert passed, f"Mean METEOR {mean:.3f} below {THRESHOLDS['meteor_mean']}"


# ── BERTScore ──────────────────────────────────────────────────────────────────

class TestBERTScore:

    def test_per_case_bertscore_f1(self, bot_outputs, bs_scores):
        """Per-case BERTScore F1 — no case below 0.70."""
        _, _, F1 = bs_scores
        failures = []
        for i, case in enumerate(bot_outputs):
            score  = F1[i].item()
            passed = score >= THRESHOLDS["bertscore_f1_min"]
            _report.add(case["id"], "BERTScore F1", score,
                        THRESHOLDS["bertscore_f1_min"], passed,
                        actual=case["output"], reference=case["reference"])
            if not passed:
                failures.append(f"{case['id']}: F1={score:.3f}")
        assert not failures, "Low BERTScore F1:\n" + "\n".join(failures)

    def test_per_case_bertscore_precision(self, bot_outputs, bs_scores):
        """Per-case BERTScore Precision — informational, floor 0.70."""
        P, _, _ = bs_scores
        for i, case in enumerate(bot_outputs):
            score = P[i].item()
            _report.add(case["id"], "BERTScore Precision", score, 0.70,
                        score >= 0.70, actual=case["output"], reference=case["reference"])

    def test_per_case_bertscore_recall(self, bot_outputs, bs_scores):
        """Per-case BERTScore Recall — informational, floor 0.70."""
        _, R, _ = bs_scores
        for i, case in enumerate(bot_outputs):
            score = R[i].item()
            _report.add(case["id"], "BERTScore Recall", score, 0.70,
                        score >= 0.70, actual=case["output"], reference=case["reference"])

    def test_mean_bertscore(self, bot_outputs, bs_scores):
        """Dataset-level mean F1, Precision, Recall."""
        P, R, F1 = bs_scores
        for name, tensor, thr in [
            ("BERTScore F1 (mean)",        F1, THRESHOLDS["bertscore_f1_mean"]),
            ("BERTScore Precision (mean)", P,  0.80),
            ("BERTScore Recall (mean)",    R,  0.80),
        ]:
            mean   = tensor.mean().item()
            passed = mean >= thr
            _report.add("dataset", name, mean, thr, passed)
        assert F1.mean().item() >= THRESHOLDS["bertscore_f1_mean"], \
            f"Mean BERTScore F1 {F1.mean().item():.3f} below {THRESHOLDS['bertscore_f1_mean']}"


# ── Exact Match ────────────────────────────────────────────────────────────────

class TestExactMatch:

    STRUCTURED = [
        {"question": "What is the express shipping cost?",   "token": "12.99"},
        {"question": "What is the return window?",           "token": "30"},
        {"question": "How do I contact support?",            "token": "support@shopeasy.com"},
    ]

    def test_exact_token_presence(self, bot_outputs):
        """Critical fact tokens (price, days, email) must appear verbatim in output."""
        from src.bot import answer
        failures = []
        for sc in self.STRUCTURED:
            output = answer(sc["question"])
            passed = sc["token"] in output
            _report.add("structured", f"Token present: '{sc['token']}'",
                        sc["token"], sc["token"], passed,
                        actual=output,
                        reference=f"must contain '{sc['token']}'",
                        note=sc["question"])
            if not passed:
                failures.append(f"'{sc['token']}' missing — Q: {sc['question']}\nOutput: {output[:120]}")
        assert not failures, "\n".join(failures)

    def test_normalised_exact_match_rate(self, bot_outputs):
        """Informational: normalised exact-match rate across the dataset."""
        for case in bot_outputs:
            match = _norm(case["output"]) == _norm(case["reference"])
            _report.add(case["id"], "Exact Match (normalised)",
                        1 if match else 0, 1, match,
                        actual=_norm(case["output"])[:200],
                        reference=_norm(case["reference"])[:200],
                        note="0=differ (expected for conversational QA)")
        matched = sum(
            1 for c in bot_outputs if _norm(c["output"]) == _norm(c["reference"])
        )
        rate = matched / len(bot_outputs)
        _report.add("dataset", "Exact Match Rate (normalised)", rate, 0.0, True,
                    note=f"{matched}/{len(bot_outputs)} — near-0% is expected for open-ended QA")
        assert rate >= 0.0
