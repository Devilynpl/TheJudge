"""Unit tests for RAG adapter and Chaos Evaluation harness."""

import asyncio
import pytest
from pathlib import Path
from typing import Any, Dict

from judgekit.rag_adapter import RAGSystemAdapter, RAGResponse
from judgekit.chaos_eval import (
    run_chaos_evaluation_suite,
    inject_chaos_bad_chunking,
    inject_chaos_top_k_drop,
    inject_chaos_sloppy_prompt,
    inject_chaos_heavy_reranker,
)


def test_rag_system_adapter_dict_pipeline():
    """Test adapter with LangChain / LlamaIndex style mock dict output."""
    class MockDoc:
        def __init__(self, text: str):
            self.page_content = text

    async def mock_arun(query: str):
        return {
            "response": "Warszawa to stolica Polski.",
            "source_documents": [MockDoc("Warszawa jest najwiekszym miastem w Polsce.")],
            "usage": {"prompt_tokens": 120, "completion_tokens": 25},
            "latency_ms": 45.2,
        }

    adapter = RAGSystemAdapter(mock_arun)
    res: RAGResponse = asyncio.run(adapter.aquery("Co to jest Warszawa?"))

    assert res.answer == "Warszawa to stolica Polski."
    assert len(res.contexts) == 1
    assert "Warszawa" in res.contexts[0]
    assert res.input_tokens == 120
    assert res.output_tokens == 25
    assert res.latency_ms == 45.2


def test_rag_system_adapter_custom_object():
    """Test adapter with object defining arun method."""
    class CustomRAGPipeline:
        async def arun(self, query: str):
            return {"answer": "Gwarancja trwa 2 lata.", "contexts": ["Tekst gwarancji"]}

    pipeline = CustomRAGPipeline()
    adapter = RAGSystemAdapter(pipeline)
    res = asyncio.run(adapter.aquery("Jaka jest gwarancja?"))

    assert res.answer == "Gwarancja trwa 2 lata."
    assert res.contexts == ["Tekst gwarancji"]



@pytest.fixture
def sample_baseline_report() -> Dict[str, Any]:
    return {
        "commit_sha": "base001",
        "branch": "main",
        "mean_faithfulness": 1.0,
        "mean_relevance": 1.0,
        "p95_latency_ms": 50.0,
        "cases": [
            {
                "test_id": f"eval-{i:03d}",
                "faithfulness_score": 1.0,
                "faithfulness_reasoning": "Spójne z kontekstem.",
                "relevance_score": 1.0,
                "relevance_reasoning": "Odpowiedź na temat.",
                "latency_ms": 40.0,
            }
            for i in range(1, 21)
        ],
    }


def test_inject_chaos_bad_chunking(sample_baseline_report):
    cand = inject_chaos_bad_chunking(sample_baseline_report)
    assert cand["branch"] == "chaos/bad-chunking"
    assert cand["mean_faithfulness"] < 1.0
    diff = [c for c in cand["cases"] if c["faithfulness_score"] == 0.0]
    assert len(diff) >= 4


def test_inject_chaos_top_k_drop(sample_baseline_report):
    cand = inject_chaos_top_k_drop(sample_baseline_report)
    assert cand["branch"] == "chaos/top-k-drop"
    assert cand["mean_faithfulness"] < 1.0


def test_inject_chaos_sloppy_prompt(sample_baseline_report):
    cand = inject_chaos_sloppy_prompt(sample_baseline_report)
    assert cand["branch"] == "chaos/sloppy-prompt"
    assert cand["mean_faithfulness"] < 1.0


def test_inject_chaos_heavy_reranker(sample_baseline_report):
    cand = inject_chaos_heavy_reranker(sample_baseline_report)
    assert cand["branch"] == "chaos/heavy-reranker"
    assert cand["p95_latency_ms"] == 500.0


def test_chaos_evaluation_suite_100_percent_detection(sample_baseline_report):
    """Verify that all 4 chaos branches are blocked by Quality Gate (100% detection rate)."""
    summary = run_chaos_evaluation_suite(sample_baseline_report)

    assert summary.total_chaos_scenarios == 4
    assert summary.total_blocked_prs == 4
    assert summary.detection_rate_pct == 100.0

    for sc in summary.scenarios:
        assert sc.gate_blocked is True
        assert sc.gate_passed is False
        assert len(sc.failure_reasons) > 0
