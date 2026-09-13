"""Unit tests for EvalRunner multi-mode metrics execution (judge, ragas, both) and tracing."""

import asyncio
import pytest
from judgekit.judge import JudgeClient
from judgekit.metrics.ragas_metrics import RagasEvaluator
from judgekit.runner import EvalRunner, RAGResult
from judgekit.schemas import TestCase
from judgekit.tracing.phoenix import PhoenixTracer


class SimpleMockRAG:
    async def aquery(self, query: str) -> RAGResult:
        return RAGResult(
            answer="Bateria robota ma gwarancję 24 miesiące.",
            contexts=["Sekcja 4.2: Gwarancja na baterię wynosi 24 miesiące."],
            input_tokens=100,
            output_tokens=20,
        )


@pytest.mark.asyncio
async def test_eval_runner_judge_only():
    rag = SimpleMockRAG()
    judge = JudgeClient(llm_client=None)
    runner = EvalRunner(rag_client=rag, judge_client=judge, metrics_mode="judge")

    tc = TestCase(
        id="c-1",
        category="factual",
        query="Ile trwa gwarancja?",
        expected_behavior="24 miesiące",
    )

    metrics = await runner.evaluate_single(tc)
    assert metrics.metrics_mode == "judge"
    assert metrics.faithfulness_score == 1.0
    assert metrics.relevance_score == 1.0
    assert metrics.ragas_faithfulness is None


@pytest.mark.asyncio
async def test_eval_runner_ragas_only():
    rag = SimpleMockRAG()
    ragas_eval = RagasEvaluator()
    runner = EvalRunner(rag_client=rag, ragas_evaluator=ragas_eval, metrics_mode="ragas")

    tc = TestCase(
        id="c-2",
        category="factual",
        query="Ile trwa gwarancja?",
        expected_behavior="24 miesiące",
        reference_answer="Gwarancja wynosi 24 miesiące.",
        reference_contexts=["Sekcja 4.2: Gwarancja na baterię wynosi 24 miesiące."],
    )

    metrics = await runner.evaluate_single(tc)
    assert metrics.metrics_mode == "ragas"
    assert metrics.ragas_faithfulness == 1.0
    assert metrics.ragas_answer_relevancy > 0.0
    assert metrics.ragas_context_precision == 1.0
    assert metrics.ragas_context_recall == 1.0
    # Downstream compatibility fields
    assert metrics.faithfulness_score == metrics.ragas_faithfulness
    assert metrics.relevance_score == metrics.ragas_answer_relevancy


@pytest.mark.asyncio
async def test_eval_runner_both_modes_and_tracing(tmp_path):
    rag = SimpleMockRAG()
    judge = JudgeClient(llm_client=None)
    ragas_eval = RagasEvaluator()
    tracer = PhoenixTracer(enabled=True)

    runner = EvalRunner(
        rag_client=rag,
        judge_client=judge,
        ragas_evaluator=ragas_eval,
        metrics_mode="both",
        tracer=tracer,
    )

    tc = TestCase(
        id="c-3",
        category="factual",
        query="Ile trwa gwarancja?",
        expected_behavior="24 miesiące",
        reference_answer="Gwarancja wynosi 24 miesiące.",
    )

    summary = await runner.run_suite([tc], commit_sha="both-sha")

    assert summary.metrics_mode == "both"
    assert summary.mean_faithfulness == 1.0
    assert summary.ragas_mean_faithfulness == 1.0
    assert summary.ragas_mean_answer_relevancy is not None
    assert summary.ragas_mean_context_precision is not None
    assert summary.ragas_mean_context_recall is not None

    # Verify tracer recorded span
    assert len(tracer.spans) == 1
    assert tracer.spans[0].test_id == "c-3"
    assert "ragas_faithfulness" in tracer.spans[0].scores

    # Verify report export contains RAGAS fields
    out_file = tmp_path / "both_report.json"
    exported = runner.export_report(summary, out_file)
    content = exported.read_text(encoding="utf-8")
    assert "ragas_mean_faithfulness" in content
    assert "ragas_mean_answer_relevancy" in content
