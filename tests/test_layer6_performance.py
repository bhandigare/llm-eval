# tests/test_layer6_performance.py — Layer 6: Performance testing
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pytest
from src.bot import answer
from src.reporter import LayerReport
from dotenv import load_dotenv

load_dotenv()

BASELINE_PATH = Path("data/perf_baseline.json")

P50_TARGET_MS  = 800
P95_TARGET_MS  = 3000
REGRESSION_PCT = 0.10
MIN_TPS        = 10
CONCURRENCY    = 3

PROBE_QUESTIONS = [
    "What is the return window?",
    "How long does standard shipping take?",
    "How do I track my order?",
    "How much does express shipping cost?",
    "How do I contact support?",
]

_report = LayerReport(
    layer_id="layer6_performance",
    layer_title="Layer 6 — Performance Testing",
    description=(
        "Latency, throughput, and regression checks. Measures p50/p95 latency against "
        "SLA targets (p50 < 800ms, p95 < 3s), token throughput under concurrent load, "
        "and compares p95 against a saved baseline (regression gate: <= +10%)."
    ),
)


def _timed(question: str) -> dict:
    start  = time.perf_counter()
    output = answer(question)
    ms     = (time.perf_counter() - start) * 1000
    return {"question": question, "output": output,
            "latency_ms": ms, "tokens": len(output.split())}


def _percentile(data: list[float], p: float) -> float:
    idx = int(len(data) * p / 100)
    return sorted(data)[min(idx, len(data) - 1)]


def _collect(n: int = 5) -> list[float]:
    qs = (PROBE_QUESTIONS * ((n // len(PROBE_QUESTIONS)) + 1))[:n]
    return [_timed(q)["latency_ms"] for q in qs]


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


@pytest.fixture(scope="module")
def latency_sample():
    return _collect(n=5)


class TestLatency:

    def test_p50_latency(self, latency_sample):
        """p50 latency must be < 800ms."""
        p50    = _percentile(latency_sample, 50)
        passed = p50 < P50_TARGET_MS
        _report.add("latency", "p50 Latency (ms)", p50, P50_TARGET_MS, passed,
                    note=f"sample size: {len(latency_sample)}")
        assert passed, f"p50 {p50:.0f}ms >= {P50_TARGET_MS}ms"

    def test_p95_latency(self, latency_sample):
        """p95 latency must be < 3000ms."""
        p95    = _percentile(latency_sample, 95)
        passed = p95 < P95_TARGET_MS
        _report.add("latency", "p95 Latency (ms)", p95, P95_TARGET_MS, passed,
                    note=f"worst 5% of {len(latency_sample)} requests")
        assert passed, f"p95 {p95:.0f}ms >= {P95_TARGET_MS}ms"

    def test_latency_distribution(self, latency_sample):
        """Record full distribution for informational use (always passes)."""
        for pct in [50, 75, 90, 95, 99]:
            val = _percentile(latency_sample, pct)
            _report.add("latency", f"p{pct} Latency (ms)", val,
                        P95_TARGET_MS if pct >= 95 else P50_TARGET_MS,
                        True, note="distribution record")


class TestThroughput:

    def test_concurrent_requests_complete(self):
        """All concurrent requests must complete without error."""
        qs      = PROBE_QUESTIONS[:CONCURRENCY]
        results = []
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for future in as_completed([pool.submit(_timed, q) for q in qs]):
                results.append(future.result())
        passed = len(results) == len(qs)
        _report.add("throughput", "Concurrent completion",
                    len(results), len(qs), passed,
                    note=f"{CONCURRENCY} parallel workers")
        assert passed

    def test_token_throughput(self):
        """Token throughput must be > MIN_TPS."""
        start, total = time.perf_counter(), 0
        for q in PROBE_QUESTIONS:
            total += _timed(q)["tokens"]
        elapsed = time.perf_counter() - start
        tps     = total / elapsed
        passed  = tps >= MIN_TPS
        _report.add("throughput", "Token Throughput (TPS)", tps, MIN_TPS, passed,
                    note=f"{total} tokens in {elapsed:.1f}s")
        assert passed, f"TPS {tps:.1f} < {MIN_TPS}"


class TestLatencyRegression:

    def test_save_baseline_if_missing(self, latency_sample):
        """Create baseline file on first run."""
        if BASELINE_PATH.exists():
            pytest.skip("Baseline already exists.")
        baseline = {
            "p50_latency_ms": _percentile(latency_sample, 50),
            "p95_latency_ms": _percentile(latency_sample, 95),
            "error_rate_pct": 0.0,
        }
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(baseline, indent=2))
        _report.add("regression", "Baseline saved", 1, 1, True,
                    note=json.dumps(baseline))

    def test_no_regression_vs_baseline(self, latency_sample):
        """p95 must not regress more than 10% vs baseline."""
        if not BASELINE_PATH.exists():
            pytest.skip("No baseline yet.")
        baseline    = json.loads(BASELINE_PATH.read_text())
        current_p95 = _percentile(latency_sample, 95)
        base_p95    = baseline["p95_latency_ms"]
        delta       = (current_p95 - base_p95) / base_p95
        passed      = delta <= REGRESSION_PCT
        _report.add("regression", "p95 Regression %", delta * 100,
                    REGRESSION_PCT * 100, passed,
                    actual=f"current p95={current_p95:.0f}ms",
                    reference=f"baseline p95={base_p95:.0f}ms",
                    note=f"delta={delta:+.1%} (gate ≤ +{REGRESSION_PCT:.0%})")
        assert passed, (f"p95 regressed {delta:+.1%} "
                        f"({base_p95:.0f}ms → {current_p95:.0f}ms)")

    def test_error_rate_under_load(self):
        """Error rate during concurrent load must be < 0.5%."""
        qs, errors = PROBE_QUESTIONS * 2, 0
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = [pool.submit(_timed, q) for q in qs]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    errors += 1
        rate   = errors / len(qs)
        passed = rate < 0.005
        _report.add("regression", "Error Rate under load", rate, 0.005, passed,
                    note=f"{errors}/{len(qs)} requests errored")
        assert passed, f"Error rate {rate:.1%} >= 0.5%"
