# llm-eval — A Hands-on Implementation of the 7-Layer LLM Testing Strategy

Production-grade evaluation framework for LLMs and AI agents, built around the
companion strategy document published on LinkedIn. Every layer of the testing
pyramid — from cheap surface metrics on every commit, through human-judged
sampling, to OWASP ASI Top 10 agent red-teaming — is implemented as runnable
pytest suites with rich HTML reports and actionable recommendations.

This is the **reference repo** for the strategy. Each layer maps 1:1 to the
strategy doc and ships with a sample bot, a golden dataset, and a published
hands-on companion article.

---

## The 7-layer pyramid at a glance

| # | Layer | What it catches | CI cadence | Cost / case |
|:-:|---|---|---|---|
| **1** | Unit metric testing | Word-level regressions, semantic drift, missing facts | Every commit | $0 |
| **2** | LLM-as-Judge | Nuanced quality (relevance, accuracy, completeness, safety) | Every PR | ~$0.001–0.01 |
| **2.5** | Ragas + MLflow | RAG-specific issues (faithfulness, context recall) | Per release | ~$0.01–0.05 |
| **3** | Human evaluation | Ground truth, edge cases, rubric calibration | Weekly | $2–10 |
| **4** | Agent trajectory | Wrong tool, malformed args, loops, goal failure | Every agent PR | ~$0.01–0.05 |
| **5** | Security red-team | Injection, jailbreak, PII leakage, OWASP ASI Top 10 | Every release | ~$0.01–0.05 |
| **6** | Performance | p50/p95 latency, throughput, regression | Per release | ~$0.05–0.20 |

---

## Quick start (5 minutes)

```bash
# 1. Clone and set up a virtualenv
git clone <this-repo>
cd llm-eval
python3 -m venv .
source bin/activate     # Windows: Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create a .env file with your OpenRouter credentials
cat > .env <<'EOF'
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASEURL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-3.5-turbo            # the bot under test
OPENROUTER_MODEL_JUDGE=openai/gpt-4.1            # a STRONGER model for the judge
OPENROUTER_EMBED_MODEL=openai/text-embedding-3-small
EOF

# 4. Download NLTK data (one-off, ~10 MB)
python -m nltk.downloader -d ~/nltk_data wordnet punkt_tab omw-1.4

# 5. Run Layer 1 and open the HTML report
pytest tests/test_layer1_metrics.py
open reports/layer1_metrics.html       # macOS — use 'xdg-open' on Linux, 'start' on Windows
```

When the run finishes, pytest prints a clickable report URL:

```
============================ HTML Reports Generated ============================
  Layer            Result    Score      Path
  ----------------------------------------------------------------------------
  layer1_metrics   HIGH      36/36 (100%)   file:///.../reports/layer1_metrics.html
```

Cmd/Ctrl-click the `file://` link in any modern terminal to open it.

---

## Prerequisites

| Requirement | Why |
|---|---|
| **Python 3.10+** | Type hints, dataclasses, modern dict syntax |
| **OpenRouter account + API key** | Multi-model gateway. One key gives access to OpenAI, Anthropic, Mistral, etc. through one API |
| **~50 MB free disk** | NLTK wordnet/punkt data + transformers cache for BERTScore (downloaded on first run) |
| **Internet access during tests** | Layers 2+ make live LLM calls; Layer 1 metric tests are fully offline once NLTK data is cached |

---

## Repository structure

```
llm-eval/
├── README.md                 ← you are here
├── requirements.txt          ← pinned dependency versions
├── conftest.py               ← shared fixtures + report summary hook
│
├── src/
│   ├── bot.py                ← the Sample Bot (ShopEasy support assistant)
│   ├── agent.py              ← tool-calling agent for Layer 4
│   ├── reporter.py           ← HTML report engine
│   └── recommendations.py    ← failure → suggested fix engine
│
├── data/
│   ├── golden_dataset.json   ← Q+A golden cases for Layers 1, 2, 2.5
│   ├── agent_tasks.yaml      ← synthetic task suite for Layer 4
│   └── perf_baseline.json    ← Layer 6 latency baseline (auto-created)
│
├── tests/
│   ├── test_layer1_metrics.py     ← BLEU, ROUGE, METEOR, BERTScore, Exact Match
│   ├── test_layer1_deepeval.py    ← DeepEval Answer Relevancy + Hallucination
│   ├── test_layer2_judge.py       ← 5-dimension LLM-as-Judge + overall
│   ├── test_layer25_ragas.py      ← Ragas faithfulness / answer relevancy / context P/R
│   ├── test_layer25_mlflow.py     ← MLflow ROUGE + toxicity + readability
│   ├── test_layer3_human.py       ← Cohen's Kappa + smart sampling
│   ├── test_layer4_agent.py       ← 9 agent metrics (Strategy v2.x Part II)
│   ├── test_layer4_agent_adversarial.py  ← Failure injection + indirect injection
│   ├── test_layer4_agent_multiturn.py    ← State consistency
│   ├── test_layer5_agent_security.py     ← OWASP ASI Top 10 (2026) red-team
│   └── test_layer6_performance.py        ← p50/p95 latency, throughput, regression
│
├── reports/                  ← HTML reports auto-generated per layer
└── docs/                     ← companion hands-on articles (.docx)
```

---

## Running tests

```bash
# Run a single layer
pytest tests/test_layer1_metrics.py

# Run all Layer 1 tests (metrics + DeepEval)
pytest tests/test_layer1_*.py

# Run everything (will hit live LLM APIs — costs ~$0.10)
pytest

# Quiet mode + write reports
pytest -q tests/test_layer4_agent.py

# Re-run only failed tests from the last run
pytest --lf

# Parallel (faster when each test makes its own LLM call)
pytest -n 4 tests/test_layer2_judge.py
```

Every test module writes its HTML report to `reports/<layer_id>.html` at the
end of the run, regardless of pass or fail.

---

## Reading the HTML reports

Each report has the same six sections:

1. **Header** — layer title, generation timestamp, total assertions, pass/fail banner
2. **Confidence Analysis** — HIGH / MEDIUM / LOW band based on pass rate + score margins
3. **Recommendations** *(only shown when failures exist)* — prioritized list of concrete bot/prompt/code fixes
4. **KPI cards** — passed, failed, total, pass-rate %
5. **Detailed Results by Metric** — collapsible per-metric tables with case ID, score, threshold, margin, result pill, expandable actual output, expandable reference, and judge reasoning
6. **Page footer** — layer ID + timestamp

### Recommendations engine

When a layer has failing assertions, the report includes an actionable
"Recommendations" panel above the score tables. Each recommendation has:

- **Priority** (HIGH / MEDIUM / LOW)
- **Category** (Bot prompt, Knowledge base, Retrieval, Tool descriptions, Security, Performance, etc.)
- **Specific file pointer** (e.g. `src/bot.py SYSTEM_PROMPT`)
- **Affected case IDs** so you know exactly which inputs reproduced the failure
- **Concrete suggested action** — a numbered plan you can apply directly

---

## Configuration

All configuration lives in `.env`. The framework never reads OS env vars
directly — it always goes through `python-dotenv`.

| Variable | Purpose | Example |
|---|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | `sk-or-v1-...` |
| `OPENROUTER_BASEURL` | OpenRouter API endpoint | `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | The bot under test (typically cheaper) | `openai/gpt-3.5-turbo` |
| `OPENROUTER_MODEL_JUDGE` | The LLM-as-Judge model (stronger than bot) | `openai/gpt-4.1` |
| `OPENROUTER_EMBED_MODEL` | Embeddings for Ragas | `openai/text-embedding-3-small` |
| `ANTHROPIC_API_KEY` | Optional, for MLflow GenAI judge metrics | `sk-ant-...` |

**Critical pattern:** the judge model should always be *stronger* than the bot
under test. Using the same model to judge itself causes self-preference bias.

---

## Using OpenAI, Claude, or Gemini instead of OpenRouter

This project uses OpenRouter by default because one API key gives you access to
every major model. If you already have an account with OpenAI, Anthropic, or
Google, you can swap the provider in two places: `src/bot.py` (the bot under
test) and the LLM wrapper in `tests/test_layer1_deepeval.py` (for DeepEval).
The same swap pattern applies to every other layer.

### Option A — OpenAI directly

**Install:** `pip install openai`

**.env:**
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini          # bot under test (cheaper)
OPENAI_MODEL_JUDGE=gpt-4o         # LLM-as-Judge (stronger)
```

**`src/bot.py`:**
```python
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

def _get_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def answer(question: str, context: str = "") -> str:
    client = _get_client()
    user_content = f"Context: {context}\n\nQuestion: {question}" if context else question
    resp = client.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
    )
    return resp.choices[0].message.content.strip()
```

**DeepEval — no wrapper needed.** DeepEval defaults to OpenAI when
`OPENAI_API_KEY` is set. Just specify the model when constructing each metric:

```python
from deepeval.metrics import AnswerRelevancyMetric
metric = AnswerRelevancyMetric(threshold=0.65, model="gpt-4o")
```

### Option B — Anthropic Claude directly

**Install:** `pip install anthropic`

**.env:**
```bash
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-20250514            # bot (cheaper, faster)
ANTHROPIC_MODEL_JUDGE=claude-opus-4-20250514       # judge (stronger)
```

**`src/bot.py`:**
```python
import anthropic
import os
from dotenv import load_dotenv
load_dotenv()

def _get_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def answer(question: str, context: str = "") -> str:
    client = _get_client()
    user_content = f"Context: {context}\n\nQuestion: {question}" if context else question
    # Claude treats system as a top-level field, not a message
    resp = client.messages.create(
        model=os.environ["ANTHROPIC_MODEL"],
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return resp.content[0].text.strip()
```

**`tests/test_layer1_deepeval.py` — replace `OpenRouterLLM` with:**
```python
import anthropic
from deepeval.models import DeepEvalBaseLLM

class ClaudeLLM(DeepEvalBaseLLM):
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model  = os.environ["ANTHROPIC_MODEL"]

    def get_model_name(self): return self._model
    def load_model(self):     return self._client

    def generate(self, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self._model, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()

    async def a_generate(self, prompt: str) -> str:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.generate, prompt)

@pytest.fixture(scope="session")
def judge():
    return ClaudeLLM()
```

### Option C — Google Gemini directly

**Install:** `pip install google-genai`

**.env:**
```bash
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash              # bot (cheaper)
GEMINI_MODEL_JUDGE=gemini-2.0-pro          # judge (stronger)
```

**`src/bot.py`:**
```python
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
load_dotenv()

def _get_client():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def answer(question: str, context: str = "") -> str:
    client = _get_client()
    user_content = f"Context: {context}\n\nQuestion: {question}" if context else question
    resp = client.models.generate_content(
        model=os.environ["GEMINI_MODEL"],
        contents=[user_content],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=300,
        ),
    )
    return resp.text.strip()
```

**`tests/test_layer1_deepeval.py` — replace `OpenRouterLLM` with:**
```python
from google import genai
from deepeval.models import DeepEvalBaseLLM

class GeminiLLM(DeepEvalBaseLLM):
    def __init__(self):
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self._model  = os.environ["GEMINI_MODEL"]

    def get_model_name(self): return self._model
    def load_model(self):     return self._client

    def generate(self, prompt: str) -> str:
        resp = self._client.models.generate_content(
            model=self._model, contents=[prompt],
        )
        return resp.text.strip()

    async def a_generate(self, prompt: str) -> str:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.generate, prompt)

@pytest.fixture(scope="session")
def judge():
    return GeminiLLM()
```

### Quick comparison

| Aspect | OpenRouter | OpenAI direct | Claude direct | Gemini direct |
|---|---|---|---|---|
| **One API for many models** | ✅ | ❌ | ❌ | ❌ |
| **Lowest latency** | adds ~50ms hop | ✅ direct | ✅ direct | ✅ direct |
| **DeepEval works out-of-box** | needs wrapper | ✅ native | needs wrapper | needs wrapper |
| **System prompt** | OpenAI-style `messages[]` | OpenAI-style | top-level `system=` field | `system_instruction` in config |
| **Response shape** | `choices[0].message.content` | same | `content[0].text` | `resp.text` |
| **Best when** | comparing across models | committed to GPT | committed to Claude | committed to Gemini |

For the other layers, the same swap pattern applies — replace the OpenRouter
client construction with the vendor's native client, then keep everything else
the same. The metric logic, thresholds, reporting, and recommendations are all
provider-agnostic.

---

## Layer status

| Layer | File(s) | Tests | Status |
|---|---|--:|---|
| 1 — Unit metrics | `test_layer1_metrics.py` | 19 | ✅ Implemented |
| 1 — DeepEval | `test_layer1_deepeval.py` | 12 | ✅ Implemented |
| 2 — LLM-as-Judge | `test_layer2_judge.py` | 10 | ✅ Implemented (5 dims + overall, v2.x) |
| 2.5 — Ragas | `test_layer25_ragas.py` | 5 | ✅ Implemented |
| 2.5 — MLflow | `test_layer25_mlflow.py` | 7 | ✅ Implemented |
| 3 — Human eval | `test_layer3_human.py` | 7 | ✅ Implemented |
| 4 — Agent trajectory | `test_layer4_agent.py` | 22 | ✅ Implemented (9 metrics) |
| 4 — Adversarial | `test_layer4_agent_adversarial.py` | 3 | ✅ Implemented |
| 4 — Multi-turn | `test_layer4_agent_multiturn.py` | 2 | ✅ Implemented |
| 5 — OWASP ASI Top 10 | `test_layer5_agent_security.py` | 11 | ✅ Implemented |
| 6 — Performance | `test_layer6_performance.py` | 7 | ✅ Implemented |

---

## Hands-on companion articles

For each layer, a detailed companion `.docx` walkthrough lives in `docs/`:

- `docs/Layer1_Unit_Testing_Implementation.docx` — Layer 1 deep dive (this one's published first)
- `docs/Layer2_LLM_Judge_Implementation.docx` — *coming next*
- `docs/Layer3_Human_Evaluation.docx` — *coming*
- `docs/Layer4_Agent_Testing.docx` — *coming*
- `docs/Layer5_Security_Red_Teaming.docx` — *coming*
- `docs/Layer6_Performance_Testing.docx` — *coming*

Each article covers:
1. Why this layer matters (linked back to the strategy doc)
2. The prerequisites (sample bot, golden dataset, etc.) and why they exist
3. Each metric in plain English
4. Beginner-friendly code excerpts (not full file dumps — read the repo for those)
5. How to read the HTML report this layer produces
6. Common pitfalls + how to calibrate thresholds for your domain

---

## Contributing

This is reference code for an evaluation strategy, not a library. Fork it,
swap in your bot, swap in your golden dataset, adjust thresholds, and ship.

When you do, please:
- Keep the per-layer module structure — it makes the strategy easy to follow
- Run `pytest tests/test_layer1_metrics.py` before committing
- Update the relevant `docs/Layer*.docx` if you change a layer's mechanics

---

## License

MIT (or your preferred license).

---

## Acknowledgements

Built on the shoulders of:
- [sacrebleu](https://github.com/mjpost/sacrebleu), [rouge-score](https://github.com/google-research/google-research/tree/master/rouge), [BERTScore](https://github.com/Tiiiger/bert_score)
- [DeepEval](https://github.com/confident-ai/deepeval)
- [Ragas](https://github.com/explodinggradients/ragas), [MLflow](https://mlflow.org/)
- [OWASP GenAI Security Project](https://owasp.org/www-project-generative-ai-security/) (ASI Top 10 2026)
