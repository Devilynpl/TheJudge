"""Unit tests for JudgeKit's dynamic Target Runner and BaseTargetAdapter protocol."""

import pytest
from typing import Optional, Dict, Any
from judgekit.target_protocol import BaseTargetAdapter, TargetOutput
from judgekit.target_runner import load_target_adapter, TargetRunnerBridge
from judgekit.schemas import TestCase, GateConfig
from judgekit.gate import evaluate_absolute_gate_rules
from judgekit.runner import RunSummary


class DummyMockAdapter(BaseTargetAdapter):
    """Test mock target adapter."""

    async def run_query(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> TargetOutput:
        if "nie wiem" in query.lower() or "unanswerable" in query.lower():
            return TargetOutput(
                answer="Dokumentacja nie zawiera tych informacji. Nie jestem w stanie odpowiedzieć.",
                contexts=[],
                latency_ms=45.0,
                status="REJECTED",
                metadata={"citation_precision": 1.0},
            )
        return TargetOutput(
            answer=f"Odpowiedź na: {query} [[źródło: test.pdf, s. 1]]",
            contexts=["test.pdf, s. 1: Treść referencyjna"],
            latency_ms=120.0,
            cost_usd=0.001,
            status="SUCCESS",
            metadata={"citation_precision": 1.0, "rubric_score": 1.0},
        )


@pytest.mark.asyncio
async def test_target_runner_bridge():
    adapter = DummyMockAdapter()
    test_case = TestCase(
        id="test-01",
        category="factual",
        query="Jaki jest limit transakcji?",
        expected_behavior="Podaj limit z cytowaniem",
    )
    bridge = TargetRunnerBridge(adapter, cases_map={test_case.query.strip().lower(): test_case})

    res = await bridge.aquery(test_case.query)
    assert isinstance(res, TargetOutput)
    assert "Odpowiedź na: Jaki jest limit transakcji?" in res.answer
    assert len(res.contexts) == 1
    assert res.latency_ms == 120.0


@pytest.mark.asyncio
async def test_target_runner_refusal():
    adapter = DummyMockAdapter()
    test_case = TestCase(
        id="test-unanswerable",
        category="unanswerable",
        query="Zapytanie o nieznany temat unanswerable",
        expected_behavior="Odmów odpowiedzi",
    )
    bridge = TargetRunnerBridge(adapter, cases_map={test_case.query.strip().lower(): test_case})

    res = await bridge.aquery(test_case.query)
    assert "nie jestem w stanie odpowiedzieć" in res.answer.lower()
    assert res.status == "REJECTED"


def test_absolute_quality_gate_evaluation():
    # Test passing gate
    pass_summary = RunSummary(
        commit_sha="abc1234",
        branch="main",
        total_cases=10,
        mean_faithfulness=0.98,
        mean_relevance=0.95,
        mean_citation_precision=0.95,
        refusal_accuracy=1.0,
        mean_rubric_score=0.90,
        stealth_accuracy=1.0,
        budget_compliance_rate=1.0,
        p50_latency_ms=100.0,
        p95_latency_ms=350.0,
        critical_failures=0,
        total_cost_usd=0.02,
    )
    cfg = GateConfig(
        min_faithfulness=0.95,
        min_citation_precision=0.90,
        require_deterministic_refusal=True,
    )
    res = evaluate_absolute_gate_rules(pass_summary, gate_config=cfg)
    assert res.passed is True
    assert len(res.failure_reasons) == 0

    # Test failing gate (low faithfulness)
    fail_summary = RunSummary(
        commit_sha="fail123",
        branch="main",
        total_cases=10,
        mean_faithfulness=0.88,  # Below 0.95
        mean_relevance=0.95,
        mean_citation_precision=0.70,  # Below 0.90
        p50_latency_ms=100.0,
        p95_latency_ms=3000.0,  # Above 2500 ms
        critical_failures=1,
        total_cost_usd=0.02,
    )
    res_fail = evaluate_absolute_gate_rules(fail_summary, gate_config=cfg)
    assert res_fail.passed is False
    assert len(res_fail.failure_reasons) >= 2
