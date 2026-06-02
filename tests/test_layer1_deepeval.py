# tests/test_layer1_deepeval.py — Layer 1: DeepEval metrics via OpenRouter
import json
import os
import pytest
from dotenv import load_dotenv
from openai import OpenAI
from deepeval import assert_test
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric, HallucinationMetric
from src.reporter import LayerReport

load_dotenv()

with open("data/golden_dataset.json") as f:
    CASES = json.load(f)

_report = LayerReport(
    layer_id="layer1_deepeval",
    layer_title="Layer 1 — DeepEval LLM Metrics",
    description=(
        "DeepEval answer relevancy and hallucination metrics, routed through OpenRouter "
        "via a custom LLM wrapper. Answer Relevancy threshold: 0.65; "
        "Hallucination threshold: 0.2 (lower = less hallucination). "
        "Every dataset case is scored individually."
    ),
)


# ── OpenRouter LLM wrapper ──────────────────────────────────────────────────────

class OpenRouterLLM(DeepEvalBaseLLM):
    def __init__(self):
        self._client = OpenAI(
            base_url=os.environ["OPENROUTER_BASEURL"],
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        self._model = os.environ["OPENROUTER_MODEL"]

    def get_model_name(self) -> str:
        return self._model

    def load_model(self):
        return self._client

    def generate(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            extra_headers={"X-Title": "DeepEval Judge"},
        )
        return resp.choices[0].message.content.strip()

    async def a_generate(self, prompt: str) -> str:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.generate, prompt)


@pytest.fixture(scope="session")
def judge():
    return OpenRouterLLM()


# ── Write report after all tests in this module ────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_answer_relevancy(case, bot_outputs, judge):
    """Each response must be relevant to the question (threshold 0.65)."""
    output  = next(o["output"] for o in bot_outputs if o["id"] == case["id"])
    metric  = AnswerRelevancyMetric(threshold=0.65, model=judge)
    tc = LLMTestCase(
        input=case["question"], actual_output=output,
        expected_output=case["reference"], context=[case.get("context", "")],
    )
    try:
        assert_test(tc, [metric])
        passed = True
        score  = metric.score if hasattr(metric, "score") else 1.0
    except AssertionError:
        passed = False
        score  = metric.score if hasattr(metric, "score") else 0.0

    _report.add(case["id"], "Answer Relevancy", score, 0.65, passed,
                actual=output, reference=case["reference"],
                note=getattr(metric, "reason", ""))
    if not passed:
        raise AssertionError(
            f"{case['id']}: Answer Relevancy={score:.3f} < 0.65. "
            f"Reason: {getattr(metric, 'reason', '')}"
        )


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_hallucination(case, bot_outputs, judge):
    """Responses must not hallucinate beyond context (threshold 0.2)."""
    output  = next(o["output"] for o in bot_outputs if o["id"] == case["id"])
    metric  = HallucinationMetric(threshold=0.2, model=judge)
    tc = LLMTestCase(
        input=case["question"], actual_output=output,
        expected_output=case["reference"], context=[case.get("context", "")],
    )
    try:
        assert_test(tc, [metric])
        passed = True
        score  = metric.score if hasattr(metric, "score") else 0.0
    except AssertionError:
        passed = False
        score  = metric.score if hasattr(metric, "score") else 1.0

    _report.add(case["id"], "Hallucination", score, 0.2, passed,
                actual=output, reference=case["reference"],
                note=getattr(metric, "reason", ""))
    if not passed:
        raise AssertionError(
            f"{case['id']}: Hallucination={score:.3f} >= 0.2. "
            f"Reason: {getattr(metric, 'reason', '')}"
        )
