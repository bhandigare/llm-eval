# tests/test_layer25_ragas.py — Layer 2.5: Ragas RAG pipeline evaluation
import json
import os
import pytest
from dotenv import load_dotenv
from src.reporter import LayerReport

load_dotenv()

with open("data/golden_dataset.json") as f:
    CASES = json.load(f)

THRESHOLDS = {
    "faithfulness":      0.80,
    "answer_relevancy":  0.75,
    "context_precision": 0.80,
    "context_recall":    0.70,
}

_report = LayerReport(
    layer_id="layer25_ragas",
    layer_title="Layer 2.5 — Ragas RAG Evaluation",
    description=(
        "Purpose-built RAG diagnostics using the Ragas framework. "
        "Faithfulness measures hallucination rate; Answer Relevancy checks on-topic focus; "
        "Context Precision/Recall measure retrieval quality. "
        "All metrics use an LLM judge routed through OpenRouter."
    ),
)


def _judge_llm():
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI
    return LangchainLLMWrapper(ChatOpenAI(
        model=os.environ["OPENROUTER_MODEL"],
        base_url=os.environ["OPENROUTER_BASEURL"],
        api_key=os.environ["OPENROUTER_API_KEY"],
    ))


def _embeddings():
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import OpenAIEmbeddings
    return LangchainEmbeddingsWrapper(OpenAIEmbeddings(
        model=os.environ.get("OPENROUTER_EMBED_MODEL", "openai/text-embedding-3-small"),
        base_url=os.environ["OPENROUTER_BASEURL"],
        api_key=os.environ["OPENROUTER_API_KEY"],
    ))


@pytest.fixture(scope="module")
def ragas_df(bot_outputs):
    from ragas import evaluate, EvaluationDataset
    from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
    llm  = _judge_llm()
    emb  = _embeddings()
    ds   = EvaluationDataset.from_list([{
        "user_input":         c["question"],
        "response":           c["output"],
        "retrieved_contexts": c.get("retrieved_contexts", [c.get("context", "")]),
        "reference":          c["reference"],
    } for c in bot_outputs])
    return evaluate(ds, metrics=[
        Faithfulness(llm=llm), AnswerRelevancy(llm=llm, embeddings=emb),
        ContextPrecision(llm=llm), ContextRecall(llm=llm),
    ]).to_pandas()


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


class TestRagas:

    def _record_metric(self, df, col, threshold, bot_outputs):
        """Add per-case rows + a mean row for a Ragas metric column."""
        if col not in df.columns:
            return
        for i, row in df.iterrows():
            case_id = bot_outputs[i]["id"] if i < len(bot_outputs) else str(i)
            score   = float(row[col]) if row[col] == row[col] else 0.0  # NaN guard
            passed  = score >= threshold
            output  = bot_outputs[i]["output"] if i < len(bot_outputs) else ""
            ref     = bot_outputs[i]["reference"] if i < len(bot_outputs) else ""
            _report.add(case_id, col.replace("_", " ").title(), score, threshold,
                        passed, actual=output, reference=ref)
        mean   = df[col].mean()
        passed = mean >= threshold
        _report.add("dataset", f"{col.replace('_', ' ').title()} (mean)", mean, threshold, passed)

    def test_faithfulness(self, ragas_df, bot_outputs):
        self._record_metric(ragas_df, "faithfulness", THRESHOLDS["faithfulness"], bot_outputs)
        mean = ragas_df["faithfulness"].mean()
        assert mean >= THRESHOLDS["faithfulness"], f"Faithfulness {mean:.3f} < {THRESHOLDS['faithfulness']}"

    def test_answer_relevancy(self, ragas_df, bot_outputs):
        self._record_metric(ragas_df, "answer_relevancy", THRESHOLDS["answer_relevancy"], bot_outputs)
        mean = ragas_df["answer_relevancy"].mean()
        assert mean >= THRESHOLDS["answer_relevancy"], f"Answer relevancy {mean:.3f} < {THRESHOLDS['answer_relevancy']}"

    def test_context_precision(self, ragas_df, bot_outputs):
        self._record_metric(ragas_df, "context_precision", THRESHOLDS["context_precision"], bot_outputs)
        mean = ragas_df["context_precision"].mean()
        assert mean >= THRESHOLDS["context_precision"], f"Context precision {mean:.3f} < {THRESHOLDS['context_precision']}"

    def test_context_recall(self, ragas_df, bot_outputs):
        self._record_metric(ragas_df, "context_recall", THRESHOLDS["context_recall"], bot_outputs)
        mean = ragas_df["context_recall"].mean()
        assert mean >= THRESHOLDS["context_recall"], f"Context recall {mean:.3f} < {THRESHOLDS['context_recall']}"

    def test_no_zero_faithfulness(self, ragas_df, bot_outputs):
        """No case may have faithfulness below 0.50 — indicates hallucination."""
        col = "faithfulness"
        if col not in ragas_df.columns:
            pytest.skip("faithfulness column not available")
        for i, row in ragas_df.iterrows():
            score  = float(row[col]) if row[col] == row[col] else 0.0
            passed = score >= 0.50
            case_id = bot_outputs[i]["id"] if i < len(bot_outputs) else str(i)
            output  = bot_outputs[i]["output"] if i < len(bot_outputs) else ""
            _report.add(case_id, "Faithfulness ≥ 0.50 (floor)", score, 0.50, passed,
                        actual=output,
                        note="< 0.50 = likely hallucination")
        bad = ragas_df[ragas_df[col] < 0.50]
        assert len(bad) == 0, f"{len(bad)} case(s) with faithfulness < 0.50"
