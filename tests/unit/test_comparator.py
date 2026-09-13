"""Unit tests for A/B Comparator, pointwise regressions and diff reports."""

import pytest
from pathlib import Path

from judgekit.comparator import compare_runs, export_diff_report, ComparisonReport


def test_compare_runs_identical_data():
    baseline_data = {
        "commit_sha": "base123",
        "mean_faithfulness": 0.90,
        "mean_relevance": 0.95,
        "p95_latency_ms": 150.0,
        "cases": [
            {
                "test_id": "eval-001",
                "faithfulness_score": 1.0,
                "relevance_score": 1.0,
                "faithfulness_reasoning": "Ok",
            },
            {
                "test_id": "eval-002",
                "faithfulness_score": 1.0,
                "relevance_score": 1.0,
                "faithfulness_reasoning": "Ok",
            },
        ],
    }

    candidate_data = dict(baseline_data)
    candidate_data["commit_sha"] = "cand456"

    report = compare_runs(baseline_data, candidate_data)

    assert report.delta_faithfulness == 0.0
    assert report.delta_relevance == 0.0
    assert report.delta_p95_latency_ms == 0.0
    assert len(report.regressions) == 0
    assert len(report.improvements) == 0
    assert report.critical_regressions_count == 0


def test_compare_runs_detects_silent_regression():
    baseline_data = {
        "commit_sha": "base123",
        "mean_faithfulness": 0.80,
        "mean_relevance": 0.80,
        "p95_latency_ms": 100.0,
        "cases": [
            {
                "test_id": "case-1",
                "faithfulness_score": 1.0,
                "relevance_score": 1.0,
                "faithfulness_reasoning": "Poprawne",
            },
            {
                "test_id": "case-2",
                "faithfulness_score": 0.0,
                "relevance_score": 1.0,
                "faithfulness_reasoning": "Brak",
            },
        ],
    }

    # In candidate, case-1 regressed (1.0 -> 0.0), but case-2 improved (0.0 -> 1.0).
    # Mean faithfulness is still 0.80 (global delta = 0), but there is 1 critical pointwise regression!
    candidate_data = {
        "commit_sha": "cand456",
        "mean_faithfulness": 0.80,
        "mean_relevance": 0.80,
        "p95_latency_ms": 110.0,
        "cases": [
            {
                "test_id": "case-1",
                "faithfulness_score": 0.0,
                "relevance_score": 1.0,
                "faithfulness_reasoning": "Halucynacja wprowadzona w nowym kodzie",
            },
            {
                "test_id": "case-2",
                "faithfulness_score": 1.0,
                "relevance_score": 1.0,
                "faithfulness_reasoning": "Poprawka",
            },
        ],
    }

    report = compare_runs(baseline_data, candidate_data)

    assert report.delta_faithfulness == 0.0
    assert len(report.regressions) == 1
    assert len(report.improvements) == 1
    assert report.critical_regressions_count == 1
    assert report.regressions[0].test_id == "case-1"
    assert report.regressions[0].diff == -1.0


def test_compare_runs_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        compare_runs("non_existent_baseline.json", "non_existent_candidate.json")


def test_export_diff_report(tmp_path):
    report = ComparisonReport(
        baseline_commit="b1",
        candidate_commit="c1",
        delta_faithfulness=0.05,
        delta_relevance=0.01,
        delta_p95_latency_ms=-15.0,
    )
    dest = tmp_path / "diff.json"
    exported = export_diff_report(report, dest)

    assert exported.exists()
    assert '"delta_faithfulness": 0.05' in exported.read_text(encoding="utf-8")


def test_compare_runs_with_ragas_metrics():
    baseline_data = {
        "commit_sha": "base1",
        "mean_faithfulness": 0.90,
        "mean_relevance": 0.90,
        "ragas_mean_faithfulness": 0.95,
        "ragas_mean_answer_relevancy": 0.92,
        "p95_latency_ms": 100.0,
        "cases": [
            {
                "test_id": "c-1",
                "faithfulness_score": 1.0,
                "relevance_score": 1.0,
                "ragas_faithfulness": 1.0,
            }
        ],
    }

    candidate_data = {
        "commit_sha": "cand2",
        "mean_faithfulness": 0.90,
        "mean_relevance": 0.90,
        "ragas_mean_faithfulness": 0.85,  # Dropped by 0.10
        "ragas_mean_answer_relevancy": 0.92,
        "p95_latency_ms": 100.0,
        "cases": [
            {
                "test_id": "c-1",
                "faithfulness_score": 1.0,
                "relevance_score": 1.0,
                "ragas_faithfulness": 0.7,
                "ragas_reasoning": {"faithfulness": "Partially unsupported claims"},
            }
        ],
    }

    report = compare_runs(baseline_data, candidate_data)

    assert report.delta_ragas_faithfulness == -0.10
    assert report.delta_ragas_answer_relevancy == 0.0
    assert any(r.metric == "ragas_faithfulness" for r in report.regressions)
    ragas_reg = next(r for r in report.regressions if r.metric == "ragas_faithfulness")
    assert ragas_reg.diff == -0.3
    assert "Partially unsupported claims" in ragas_reg.reason
