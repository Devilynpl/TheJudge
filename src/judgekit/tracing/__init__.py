"""Tracing module for JudgeKit evaluation pipeline.

Integrates Arize Phoenix tracing for RAG retrieval and evaluation observability.
"""

from judgekit.tracing.phoenix import PhoenixTracer, PhoenixSpan

__all__ = ["PhoenixTracer", "PhoenixSpan"]
