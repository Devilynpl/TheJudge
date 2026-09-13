"""Unit tests for PhoenixTracer and PhoenixSpan."""

import pytest
from pathlib import Path
from judgekit.tracing.phoenix import PhoenixTracer, PhoenixSpan


def test_phoenix_tracer_disabled_by_default():
    tracer = PhoenixTracer(enabled=False)
    assert tracer.enabled is False

    span = tracer.log_span(
        test_id="case-1",
        query="test query",
        retrieved_contexts=["ctx 1"],
        final_answer="test answer",
        scores={"faithfulness": 1.0},
        latency_ms=120.5,
    )

    assert span is None
    assert len(tracer.spans) == 0


def test_phoenix_tracer_enabled_records_spans(tmp_path):
    tracer = PhoenixTracer(enabled=True, project_name="unit-test-eval")
    assert tracer.enabled is True

    span = tracer.log_span(
        test_id="case-101",
        query="Co to jest RAG?",
        retrieved_contexts=["RAG to Retrieval-Augmented Generation."],
        final_answer="RAG to technika łączenia wyszukiwania z generowaniem tekstu.",
        scores={
            "faithfulness": 1.0,
            "relevance": 1.0,
            "ragas_faithfulness": 0.95,
            "ragas_answer_relevancy": 0.98,
        },
        latency_ms=85.2,
        tokens_input=120,
        tokens_output=25,
    )

    assert span is not None
    assert isinstance(span, PhoenixSpan)
    assert span.test_id == "case-101"
    assert span.scores["ragas_faithfulness"] == 0.95
    assert len(tracer.spans) == 1

    # Test export to JSONL
    out_file = tmp_path / "phoenix_spans.jsonl"
    exported = tracer.export_traces_jsonl(out_file)
    assert exported is not None
    assert exported.exists()
    content = exported.read_text(encoding="utf-8")
    assert "case-101" in content
    assert "ragas_faithfulness" in content


def test_phoenix_tracer_env_flag(monkeypatch):
    monkeypatch.setenv("JUDGEKIT_TRACE_PHOENIX", "1")
    tracer = PhoenixTracer()
    assert tracer.enabled is True

    monkeypatch.setenv("JUDGEKIT_TRACE_PHOENIX", "0")
    tracer_off = PhoenixTracer()
    assert tracer_off.enabled is False
