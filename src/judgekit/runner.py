"""Evaluation Runner and performance/cost measurement engine.

Implements:
- Asyncio concurrency control with Semaphore (rate limit protection)
- High-precision latency measurement (time.perf_counter)
- Token consumption and dollar cost calculation
- Non-linear statistical percentiles (P50, P95) and failure rate aggregation
- JSON evaluation snapshot export (artifacts/eval_run_<commit_sha>.json)
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union
import numpy as np
from pydantic import BaseModel, Field

from judgekit.schemas import PipelineMetrics, TestCase


class RAGResult(BaseModel):
    """Normalized response returned from an evaluated RAG pipeline."""

    answer: str
    contexts: List[str] = Field(default_factory=list)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class RAGClientProtocol(Protocol):
    """Protocol for evaluated RAG systems."""

    async def aquery(self, query: str) -> Any:
        ...


class RunSummary(BaseModel):
    """Statistical aggregation of an evaluation run."""

    commit_sha: str = Field(default="local", description="Git commit hash of evaluated code.")
    branch: str = Field(default="main", description="Git branch name.")
    total_cases: int = Field(..., description="Total number of evaluated test cases.")
    mean_faithfulness: float = Field(..., description="Average faithfulness score.")
    mean_relevance: float = Field(..., description="Average answer relevance score.")
    mean_citation_precision: Optional[float] = Field(default=None, description="Average citation precision score.")
    refusal_accuracy: Optional[float] = Field(default=None, description="Deterministic refusal accuracy for unanswerables.")
    mean_rubric_score: Optional[float] = Field(default=None, description="Average rubric agreement score (for agent briefs).")
    stealth_accuracy: Optional[float] = Field(default=None, description="Zero-hallucination accuracy for stealth entities.")
    budget_compliance_rate: Optional[float] = Field(default=None, description="Fraction of runs compliant with hard budgets.")
    avg_steps: Optional[float] = Field(default=None, description="Average steps taken per run.")
    p50_latency_ms: float = Field(..., description="Median P50 latency in milliseconds.")
    p95_latency_ms: float = Field(..., description="95th percentile latency in milliseconds.")
    critical_failures: int = Field(..., description="Number of critical failures (faithfulness == 0.0).")
    total_cost_usd: float = Field(..., description="Total estimated cost in USD.")
    cases: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed per-case results.")


def compute_run_summary(
    results: List[PipelineMetrics],
    commit_sha: str = "unknown",
    branch: str = "main",
) -> RunSummary:
    """Compute statistical percentiles, averages and failure counts across evaluated cases.

    Args:
        results: List of evaluated PipelineMetrics.
        commit_sha: Commit hash.
        branch: Branch name.

    Returns:
        Aggregated RunSummary model.
    """
    if not results:
        raise ValueError("Cannot compute summary on empty results.")

    latencies = [r.latency_ms for r in results]
    faith_scores = [r.faithfulness_score for r in results]
    rel_scores = [r.relevance_score for r in results]
    costs = [r.cost_usd for r in results]

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    mean_faith = float(np.mean(faith_scores))
    mean_rel = float(np.mean(rel_scores))
    crit_failures = sum(1 for s in faith_scores if s == 0.0)
    total_cost = float(sum(costs))

    # Extended metrics
    cit_precisions = [r.citation_precision for r in results if r.citation_precision is not None]
    mean_cit_prec = float(np.mean(cit_precisions)) if cit_precisions else None

    refusals = [r.refusal_correct for r in results if r.refusal_correct is not None]
    refusal_acc = float(np.mean([1.0 if v else 0.0 for v in refusals])) if refusals else None

    rubrics = [r.rubric_score for r in results if r.rubric_score is not None]
    mean_rubric = float(np.mean(rubrics)) if rubrics else None

    stealths = [r.stealth_verified for r in results if r.stealth_verified is not None]
    stealth_acc = float(np.mean([1.0 if v else 0.0 for v in stealths])) if stealths else None

    budgets = [r.budget_compliant for r in results if r.budget_compliant is not None]
    budget_rate = float(np.mean([1.0 if v else 0.0 for v in budgets])) if budgets else None

    steps = [r.step_count for r in results if r.step_count is not None]
    avg_step_count = float(np.mean(steps)) if steps else None

    cases_dump = [r.model_dump() for r in results]

    return RunSummary(
        commit_sha=commit_sha,
        branch=branch,
        total_cases=len(results),
        mean_faithfulness=round(mean_faith, 4),
        mean_relevance=round(mean_rel, 4),
        mean_citation_precision=round(mean_cit_prec, 4) if mean_cit_prec is not None else None,
        refusal_accuracy=round(refusal_acc, 4) if refusal_acc is not None else None,
        mean_rubric_score=round(mean_rubric, 4) if mean_rubric is not None else None,
        stealth_accuracy=round(stealth_acc, 4) if stealth_acc is not None else None,
        budget_compliance_rate=round(budget_rate, 4) if budget_rate is not None else None,
        avg_steps=round(avg_step_count, 2) if avg_step_count is not None else None,
        p50_latency_ms=round(p50, 2),
        p95_latency_ms=round(p95, 2),
        critical_failures=crit_failures,
        total_cost_usd=round(total_cost, 6),
        cases=cases_dump,
    )


class EvalRunner:
    """Async evaluation runner executing tests concurrently with semaphore rate limiting."""

    def __init__(
        self,
        rag_client: Any,
        judge_client: Any,
        max_concurrency: int = 10,
        cost_per_1m_input: float = 0.15,
        cost_per_1m_output: float = 0.60,
    ):
        """Initialize the EvalRunner.

        Args:
            rag_client: Evaluated RAG client instance implementing aquery(query).
            judge_client: JudgeClient instance implementing a_eval_faithfulness and a_eval_relevance.
            max_concurrency: Maximum number of concurrent executions (asyncio Semaphore).
            cost_per_1m_input: Cost in USD per 1M prompt/input tokens.
            cost_per_1m_output: Cost in USD per 1M completion/output tokens.
        """
        self.rag = rag_client
        self.judge = judge_client
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.cost_per_1m_input = cost_per_1m_input
        self.cost_per_1m_output = cost_per_1m_output

    async def evaluate_single(self, test_case: Union[TestCase, Dict[str, Any]]) -> PipelineMetrics:
        """Evaluate a single test case with latency, token usage and parallel judge scoring."""
        if isinstance(test_case, dict):
            tc = TestCase.model_validate(test_case)
        else:
            tc = test_case

        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                # 1. Query evaluated RAG system
                raw_rag_response = await self.rag.aquery(tc.query)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                # Normalize RAG response
                if hasattr(raw_rag_response, "answer"):
                    answer = raw_rag_response.answer
                    contexts = getattr(raw_rag_response, "contexts", []) or getattr(raw_rag_response, "context", [])
                    inp_tokens = getattr(raw_rag_response, "input_tokens", 0)
                    out_tokens = getattr(raw_rag_response, "output_tokens", 0)
                elif isinstance(raw_rag_response, dict):
                    answer = raw_rag_response.get("answer", "")
                    contexts = raw_rag_response.get("contexts", [])
                    inp_tokens = raw_rag_response.get("input_tokens", 0)
                    out_tokens = raw_rag_response.get("output_tokens", 0)
                else:
                    answer = str(raw_rag_response)
                    contexts = []
                    inp_tokens = 0
                    out_tokens = 0

                # Ensure contexts is a list
                if isinstance(contexts, str):
                    contexts = [contexts]

                # 2. Parallel Judge evaluation (Faithfulness + Relevance)
                faith_task = self.judge.a_eval_faithfulness(
                    context=contexts,
                    answer=answer,
                )
                rel_task = self.judge.a_eval_relevance(
                    query=tc.query,
                    answer=answer,
                )

                faith_verdict, rel_verdict = await asyncio.gather(faith_task, rel_task)

                # 3. Target metadata extraction (citations, refusals, rubric, budgets)
                cit_precision = None
                refusal_correct = None
                rubric_score = None
                stealth_verified = None
                budget_compliant = None
                step_count = getattr(raw_rag_response, "step_count", None)
                status = getattr(raw_rag_response, "status", None)
                cost_override = getattr(raw_rag_response, "cost_usd", 0.0)
                meta = getattr(raw_rag_response, "metadata", {}) or {}

                # Citation precision extraction
                if "citation_precision" in meta:
                    cit_precision = float(meta["citation_precision"])
                elif re.findall(r"\[\[.*?\]\]", answer):
                    # Check citations against contexts
                    citations = re.findall(r"\[\[.*?\]\]", answer)
                    valid_cits = sum(1 for c in citations if any(c.strip("[]") in ctx for ctx in contexts))
                    cit_precision = valid_cits / len(citations) if citations else 1.0

                # Deterministic refusal check for out-of-domain / unanswerables
                is_unanswerable = any(
                    term in tc.category.lower() or term in tc.expected_behavior.lower()
                    for term in ["unanswerable", "out_of_domain", "nie wiem", "brak informacji", "refuse"]
                )
                if is_unanswerable:
                    refusal_keywords = [
                        "nie jestem w stanie odpowiedzieć",
                        "brak pasujących informacji",
                        "dokumentacja nie zawiera",
                        "nie wiem",
                        "unverifiable",
                    ]
                    refusal_correct = any(rk in answer.lower() for rk in refusal_keywords)

                # Stealth / phantom company verification
                if "stealth" in tc.category.lower() or "adversarial" in tc.category.lower() or "phantom" in tc.category.lower():
                    stealth_verified = (status == "UNVERIFIABLE_COMPANY") or ("unverifiable" in answer.lower())

                # Rubric check
                if "rubric_score" in meta:
                    rubric_score = float(meta["rubric_score"])

                # Budget compliance
                max_steps_allowed = meta.get("max_steps", 12)
                max_cost_allowed = meta.get("max_cost_usd", 0.15)
                budget_compliant = (step_count is None or step_count <= max_steps_allowed) and (
                    cost_override <= max_cost_allowed
                )

                # 4. Calculate operational cost
                calc_cost = (
                    (inp_tokens * self.cost_per_1m_input) + (out_tokens * self.cost_per_1m_output)
                ) / 1_000_000.0
                final_cost = cost_override if cost_override > 0 else calc_cost

                return PipelineMetrics(
                    test_id=tc.id,
                    latency_ms=round(latency_ms, 2),
                    input_tokens=inp_tokens,
                    output_tokens=out_tokens,
                    cost_usd=round(final_cost, 6),
                    faithfulness_score=faith_verdict.score,
                    relevance_score=rel_verdict.score,
                    citation_precision=cit_precision,
                    refusal_correct=refusal_correct,
                    rubric_score=rubric_score,
                    stealth_verified=stealth_verified,
                    budget_compliant=budget_compliant,
                    step_count=step_count,
                    faithfulness_reasoning=faith_verdict.reasoning,
                    relevance_reasoning=rel_verdict.reasoning,
                )
            except Exception as err:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return PipelineMetrics(
                    test_id=tc.id,
                    latency_ms=round(latency_ms, 2),
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    faithfulness_score=0.0,
                    relevance_score=0.0,
                    faithfulness_reasoning=f"Execution error: {str(err)}",
                    relevance_reasoning=f"Execution error: {str(err)}",
                )


    async def run_suite(
        self,
        test_cases: List[Union[TestCase, Dict[str, Any]]],
        commit_sha: str = "unknown",
        branch: str = "main",
    ) -> RunSummary:
        """Run evaluation across all test cases and return aggregated summary."""
        tasks = [self.evaluate_single(tc) for tc in test_cases]
        results = await asyncio.gather(*tasks)
        return compute_run_summary(results, commit_sha=commit_sha, branch=branch)

    def export_report(self, summary: RunSummary, output_path: Union[str, Path]) -> Path:
        """Save evaluation summary and cases to JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)
        return path
