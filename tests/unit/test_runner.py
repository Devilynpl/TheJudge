"""Unit tests for EvalRunner, concurrency control, percentiles and report export."""

import asyncio
import pytest
from pathlib import Path

from judgekit.judge import JudgeClient
from judgekit.runner import (
    EvalRunner,
    RAGResult,
    RunSummary,
    compute_run_summary,
)
from judgekit.schemas import PipelineMetrics, TestCase


class MockRAGSystem:
    """Mock RAG system simulating variable latency and token generation."""

    def __init__(self, latency_delay: float = 0.01):
        self.latency_delay = latency_delay

    async def aquery(self, query: str) -> RAGResult:
        await asyncio.sleep(self.latency_delay)
        return RAGResult(
            answer=f"Odpowiedź na: {query}",
            contexts=["Kontekst 1", "Kontekst 2"],
            input_tokens=150,
            output_tokens=30,
        )


def test_compute_run_summary_percentiles():
    metrics = [
        PipelineMetrics(
            test_id=f"t-{i}",
            latency_ms=10.0 * i,
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.00005,
            faithfulness_score=1.0 if i < 9 else 0.0,
            relevance_score=1.0,
        )
        for i in range(1, 11)
    ]

    summary = compute_run_summary(metrics, commit_sha="abc1234", branch="feature/test")

    assert summary.total_cases == 10
    assert summary.p50_latency_ms == 55.0  # Median of 10, 20, ..., 100
    assert summary.p95_latency_ms == pytest.approx(95.5, abs=1.0)
    assert summary.critical_failures == 2  # i=9 and i=10 have 0.0 score
    assert summary.mean_faithfulness == 0.8
    assert summary.total_cost_usd == pytest.approx(0.0005, rel=1e-3)
    assert summary.commit_sha == "abc1234"


def test_eval_runner_suite_execution(tmp_path):
    rag = MockRAGSystem(latency_delay=0.005)
    judge = JudgeClient(llm_client=None)
    runner = EvalRunner(rag_client=rag, judge_client=judge, max_concurrency=5)

    test_cases = [
        TestCase(
            id=f"case-{i}",
            category="factual",
            query=f"Pytanie {i}",
            expected_behavior="Zgodne z kontekstem.",
        )
        for i in range(5)
    ]

    summary = asyncio.run(runner.run_suite(test_cases, commit_sha="testsha", branch="main"))

    assert summary.total_cases == 5
    assert summary.mean_faithfulness == 1.0
    assert summary.p50_latency_ms > 0

    # Test report export
    out_file = tmp_path / "eval_report.json"
    exported_path = runner.export_report(summary, out_file)
    assert exported_path.exists()
    assert '"commit_sha": "testsha"' in exported_path.read_text(encoding="utf-8")


def test_eval_runner_concurrency_semaphore():
    # Verify semaphore limits concurrent running tasks
    active_concurrent = 0
    max_observed = 0

    class ConcurrencyTrackingRAG:
        async def aquery(self, query: str):
            nonlocal active_concurrent, max_observed
            active_concurrent += 1
            max_observed = max(max_observed, active_concurrent)
            await asyncio.sleep(0.02)
            active_concurrent -= 1
            return RAGResult(answer="ok", contexts=[], input_tokens=10, output_tokens=10)

    rag = ConcurrencyTrackingRAG()
    judge = JudgeClient(llm_client=None)
    runner = EvalRunner(rag_client=rag, judge_client=judge, max_concurrency=3)

    cases = [
        TestCase(id=f"c-{i}", category="factual", query="q", expected_behavior="b")
        for i in range(10)
    ]

    asyncio.run(runner.run_suite(cases))
    assert max_observed <= 3
