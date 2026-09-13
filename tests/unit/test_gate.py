"""Unit tests for Quality Gate decision enforcement and rules."""

import pytest
from pathlib import Path

from judgekit.gate import evaluate_gate_rules, QualityGateResult


def test_evaluate_gate_rules_pass():
    diff_data = {
        "delta_faithfulness": 0.01,
        "delta_relevance": 0.02,
        "delta_p95_latency_ms": 50.0,
        "regressions": [],
    }

    result = evaluate_gate_rules(diff_data)
    assert result.passed is True
    assert len(result.failure_reasons) == 0


def test_evaluate_gate_rules_fail_on_faithfulness_drop():
    diff_data = {
        "delta_faithfulness": -0.05,  # Drop > 0.02
        "delta_relevance": 0.0,
        "delta_p95_latency_ms": 10.0,
        "regressions": [],
    }

    result = evaluate_gate_rules(diff_data, max_faithfulness_drop=0.02)
    assert result.passed is False
    assert any("Zbyt duży spadek" in r for r in result.failure_reasons)


def test_evaluate_gate_rules_fail_on_critical_regression():
    diff_data = {
        "delta_faithfulness": 0.02,
        "delta_relevance": 0.0,
        "delta_p95_latency_ms": 10.0,
        "regressions": [
            {
                "test_id": "eval-015",
                "diff": -1.0,  # Critical regression (e.g. 1.0 -> 0.0)
                "baseline_score": 1.0,
                "candidate_score": 0.0,
                "reason": "Halucynacja warunków gwarancji.",
            }
        ],
    }

    result = evaluate_gate_rules(diff_data, max_critical_regressions=0)
    assert result.passed is False
    assert len(result.critical_regressions) == 1
    assert any("krytycznych regresji" in r for r in result.failure_reasons)


def test_evaluate_gate_rules_fail_on_latency_slo_breach():
    diff_data = {
        "delta_faithfulness": 0.01,
        "delta_relevance": 0.0,
        "delta_p95_latency_ms": 320.0,  # Increase > 250ms
        "regressions": [],
    }

    result = evaluate_gate_rules(diff_data, max_p95_latency_increase_ms=250.0)
    assert result.passed is False
    assert any("opóźnienia P95" in r for r in result.failure_reasons)


def test_evaluate_gate_rules_fail_on_ragas_faithfulness_drop():
    diff_data = {
        "delta_faithfulness": 0.0,
        "delta_relevance": 0.0,
        "delta_p95_latency_ms": 10.0,
        "delta_ragas_faithfulness": -0.05,  # Drop > 0.03
        "regressions": [],
    }

    result = evaluate_gate_rules(diff_data, max_ragas_faithfulness_drop=0.03)
    assert result.passed is False
    assert any("wierności RAGAS" in r for r in result.failure_reasons)


def test_evaluate_absolute_gate_rules_with_ragas_config():
    from judgekit.gate import evaluate_absolute_gate_rules
    from judgekit.schemas import GateConfig

    summary_data = {
        "mean_faithfulness": 0.98,
        "mean_relevance": 0.95,
        "p95_latency_ms": 150.0,
        "critical_failures": 0,
        "ragas_mean_faithfulness": 0.82,  # below 0.90
        "ragas_mean_answer_relevancy": 0.95,
    }

    cfg = GateConfig(min_ragas_faithfulness=0.90)
    result = evaluate_absolute_gate_rules(summary_data, gate_config=cfg)

    assert result.passed is False
    assert any("Wierność RAGAS" in r for r in result.failure_reasons)

