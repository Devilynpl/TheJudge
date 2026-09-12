"""Tests for JudgeKit data contracts and Pydantic schemas."""

import pytest
from pydantic import ValidationError

from judgekit.schemas import (
    TestCase,
    RunOutput,
    MetricEvaluation,
    JudgeReport,
    PipelineMetrics,
)


def test_test_case_valid():
    tc = TestCase(
        id="eval-001",
        category="factual",
        query="What is the warranty period for the battery?",
        expected_behavior="State exactly 24 months based on section 4.2.",
        reference_answer="The battery warranty is 24 months.",
        reference_contexts=["Section 4.2: Battery warranty is 24 months."],
    )
    assert tc.id == "eval-001"
    assert tc.category == "factual"
    assert len(tc.reference_contexts) == 1


def test_test_case_optional_fields():
    tc = TestCase(
        id="eval-002",
        category="unanswerable",
        query="Do you offer free weekend pickup?",
        expected_behavior="State that documentation does not mention weekend pickup.",
    )
    assert tc.reference_answer is None
    assert tc.reference_contexts is None


def test_test_case_missing_required_fields():
    with pytest.raises(ValidationError):
        TestCase(id="eval-003", category="factual")


def test_run_output_valid():
    ro = RunOutput(
        test_case_id="eval-001",
        generated_answer="The battery warranty is 24 months.",
        retrieved_contexts=["Context chunk 1"],
        latency_ms=124.5,
        tokens_input=150,
        tokens_output=25,
    )
    assert ro.test_case_id == "eval-001"
    assert ro.latency_ms == 124.5
    assert ro.tokens_input == 150


def test_run_output_negative_latency_invalid():
    with pytest.raises(ValidationError):
        RunOutput(
            test_case_id="eval-001",
            generated_answer="Test",
            latency_ms=-10.0,
        )


def test_metric_evaluation_valid():
    me = MetricEvaluation(
        reasoning="Step 1: All claims in answer are backed by context.",
        score=1.0,
    )
    assert me.score == 1.0
    assert "Step 1" in me.reasoning


def test_metric_evaluation_score_bounds():
    with pytest.raises(ValidationError):
        MetricEvaluation(reasoning="Invalid high score", score=1.5)

    with pytest.raises(ValidationError):
        MetricEvaluation(reasoning="Invalid low score", score=-0.1)


def test_metric_evaluation_chain_of_thought_enforcement():
    # Empty reasoning must fail validation
    with pytest.raises(ValidationError):
        MetricEvaluation(reasoning="", score=0.8)

    with pytest.raises(ValidationError):
        MetricEvaluation(reasoning="   ", score=0.8)


def test_judge_report_valid():
    report = JudgeReport(
        test_case_id="eval-001",
        faithfulness=MetricEvaluation(
            reasoning="Context explicitly states 24 months warranty. Answer matches completely.",
            score=1.0,
        ),
        answer_relevance=MetricEvaluation(
            reasoning="Directly answers user's query about warranty.",
            score=1.0,
        ),
        safety=MetricEvaluation(
            reasoning="No harmful or toxic content detected.",
            score=1.0,
        ),
    )
    assert report.test_case_id == "eval-001"
    assert report.context_relevance is None
    assert report.faithfulness.score == 1.0


def test_pipeline_metrics_valid():
    pm = PipelineMetrics(
        test_id="eval-001",
        latency_ms=145.2,
        input_tokens=200,
        output_tokens=30,
        cost_usd=0.000048,
        faithfulness_score=1.0,
        relevance_score=1.0,
        faithfulness_reasoning="Ground truth verified.",
        relevance_reasoning="Direct response provided.",
    )
    assert pm.test_id == "eval-001"
    assert pm.latency_ms == 145.2
    assert pm.cost_usd == 0.000048
