"""RAG system adapter and simulation harness for JudgeKit evaluations."""

import inspect
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Protocol, Union
from pydantic import BaseModel, Field


class RAGResponse(NamedTuple):
    """Normalized response contract returned by RAG systems."""

    answer: str
    contexts: List[str]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0


class RAGPipelineProtocol(Protocol):
    """Structural typing protocol for RAG pipeline instances."""

    async def arun(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        ...


class RAGSystemAdapter:
    """Adapter bridging arbitrary RAG architectures into JudgeKit evaluation format."""

    def __init__(self, rag_pipeline: Any):
        self.pipeline = rag_pipeline

    async def aquery(self, query: str, **kwargs: Any) -> RAGResponse:
        """Query the underlying RAG system asynchronously and normalize output.

        Handles:
        - LangChain / LlamaIndex style dict outputs (`response`, `source_documents`, `usage`)
        - Callable async functions returning dict or string
        - Direct RAGResponse objects
        """
        # Case 1: Callable function or method
        if callable(self.pipeline):
            if inspect.iscoroutinefunction(self.pipeline):
                raw = await self.pipeline(query, **kwargs)
            else:
                raw = self.pipeline(query, **kwargs)
        # Case 2: Pipeline object with arun or aquery
        elif hasattr(self.pipeline, "arun"):
            raw = await self.pipeline.arun(query, **kwargs)
        elif hasattr(self.pipeline, "aquery"):
            raw = await self.pipeline.aquery(query, **kwargs)
        elif hasattr(self.pipeline, "run"):
            raw = self.pipeline.run(query, **kwargs)
        else:
            raise AttributeError(f"Unsupported pipeline object: {type(self.pipeline)}")

        # Normalize to RAGResponse
        if isinstance(raw, RAGResponse):
            return raw

        if isinstance(raw, dict):
            answer = raw.get("response") or raw.get("answer") or raw.get("output") or ""
            
            # Extract source contexts
            contexts: List[str] = []
            src_docs = raw.get("source_documents") or raw.get("contexts") or raw.get("sources") or []
            for doc in src_docs:
                if hasattr(doc, "page_content"):
                    contexts.append(str(doc.page_content))
                elif isinstance(doc, dict):
                    contexts.append(str(doc.get("content") or doc.get("text") or ""))
                else:
                    contexts.append(str(doc))

            usage = raw.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            lat = float(raw.get("latency_ms", 0.0))

            return RAGResponse(
                answer=str(answer),
                contexts=contexts,
                input_tokens=int(prompt_tokens),
                output_tokens=int(completion_tokens),
                latency_ms=lat,
            )

        # Fallback string
        return RAGResponse(
            answer=str(raw),
            contexts=[],
            input_tokens=0,
            output_tokens=0,
            latency_ms=0.0,
        )
