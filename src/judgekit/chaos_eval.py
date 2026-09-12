"""Chaos evaluation engine and synthetic regression injectors.

Simulates 4 common failure modes in RAG systems:
1. chaos/bad-chunking (chunk size reduced 512 -> 128, breaking multi-hop facts)
2. chaos/top-k-drop (top_k dropped 5 -> 1, causing missing contexts & hallucinations)
3. chaos/sloppy-prompt (omits 'say I don't know', hallucinating on unanswerable questions)
4. chaos/heavy-reranker (slow cross-encoder adding latency, breaching P95 SLO)

Computes the Regression Detection Rate (%) of the JudgeKit Quality Gate.
"""

import copy
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from pydantic import BaseModel, Field

from judgekit.comparator import compare_runs, ComparisonReport
from judgekit.gate import evaluate_gate_rules, QualityGateResult
from judgekit.schemas import JudgeReport


class ChaosScenarioResult(BaseModel):
    """Result of running a single chaos regression experiment through JudgeKit."""

    branch_name: str
    injected_failure: str
    expected_failure_mode: str
    gate_passed: bool
    gate_blocked: bool
    delta_faithfulness: float
    delta_relevance: float
    delta_p95_latency_ms: float
    critical_regressions: int
    failure_reasons: List[str]


class ChaosEvaluationSummary(BaseModel):
    """Aggregated chaos experiment summary and detection rate metric."""

    total_chaos_scenarios: int
    total_blocked_prs: int
    detection_rate_pct: float
    scenarios: List[ChaosScenarioResult]


def inject_chaos_bad_chunking(baseline_report: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate 'chaos/bad-chunking' scenario:

    Chunk size reduced from 512 to 128 tokens.
    Causes facts in multi-hop queries (e.g. eval-002, eval-005, eval-010) to fragment.
    Faithfulness drops drastically across several cases.
    """
    candidate = copy.deepcopy(baseline_report)
    candidate["branch"] = "chaos/bad-chunking"
    candidate["commit_sha"] = "chaos_chunk_01"

    # Degrade faithfulness on multi-hop cases
    affected_ids = {"eval-002", "eval-005", "eval-009", "eval-014"}
    for case in candidate.get("cases", []):
        if case["test_id"] in affected_ids:
            case["faithfulness_score"] = 0.0
            case["faithfulness_reasoning"] = (
                "Kontekst zostal pofragmentowany na zbyt male chunki (128 tokenow). "
                "Odpowiedz pomija polaczenie pomiedzy warunkami i halucynuje brakujacy fakt."
            )

    # Recompute mean faithfulness
    scores = [c["faithfulness_score"] for c in candidate.get("cases", [])]
    candidate["mean_faithfulness"] = round(sum(scores) / len(scores), 4) if scores else 0.0
    return candidate


def inject_chaos_top_k_drop(baseline_report: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate 'chaos/top-k-drop' scenario:

    Top-k reduced from 5 to 1 document.
    Missing key documentary evidence causes the model to invent answers (hallucinate).
    """
    candidate = copy.deepcopy(baseline_report)
    candidate["branch"] = "chaos/top-k-drop"
    candidate["commit_sha"] = "chaos_topk_02"

    affected_ids = {"eval-003", "eval-007", "eval-015"}
    for case in candidate.get("cases", []):
        if case["test_id"] in affected_ids:
            case["faithfulness_score"] = 0.0
            case["faithfulness_reasoning"] = (
                "W prompcie zabraklo kluczowego dokumentu (retrieval top_k=1). "
                "Model wymyslil nieistniejace parametry techniczne bez oparcia w tekscie."
            )

    scores = [c["faithfulness_score"] for c in candidate.get("cases", [])]
    candidate["mean_faithfulness"] = round(sum(scores) / len(scores), 4) if scores else 0.0
    return candidate


def inject_chaos_sloppy_prompt(baseline_report: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate 'chaos/sloppy-prompt' scenario:

    Developer removes grounding guardrail: 'If context doesn't contain answer, say I don't know'.
    Causes critical drops (1.0 -> 0.0) on out-of-domain / unanswerable questions.
    """
    candidate = copy.deepcopy(baseline_report)
    candidate["branch"] = "chaos/sloppy-prompt"
    candidate["commit_sha"] = "chaos_prompt_03"

    affected_ids = {"eval-004", "eval-018"}
    for case in candidate.get("cases", []):
        if case["test_id"] in affected_ids:
            case["faithfulness_score"] = 0.0
            case["faithfulness_reasoning"] = (
                "Zapytanie dotyczy faktow spoza bazy wiedzy. "
                "Z powodu usuniecia instrukcji 'powiedz nie wiem', model odpowiedzial z wiedzy ogolnej (halucynacja)."
            )

    scores = [c["faithfulness_score"] for c in candidate.get("cases", [])]
    candidate["mean_faithfulness"] = round(sum(scores) / len(scores), 4) if scores else 0.0
    return candidate


def inject_chaos_heavy_reranker(baseline_report: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate 'chaos/heavy-reranker' scenario:

    A complex cross-encoder reranker is added to the retrieval step.
    Quality is preserved (+0.00), but P95 latency breaches SLO (+450 ms > +250 ms).
    """
    candidate = copy.deepcopy(baseline_report)
    candidate["branch"] = "chaos/heavy-reranker"
    candidate["commit_sha"] = "chaos_rerank_04"

    # Add 450 ms to P95 latency
    base_p95 = float(candidate.get("p95_latency_ms", 50.0))
    candidate["p95_latency_ms"] = round(base_p95 + 450.0, 2)
    return candidate


CHAOS_SCENARIOS = [
    (
        "chaos/bad-chunking",
        "Zmniejszenie chunk size z 512 do 128 tokenow",
        "Drastyczny spadek Faithfulness w zapytaniach multi-hop",
        inject_chaos_bad_chunking,
    ),
    (
        "chaos/top-k-drop",
        "Zmniejszenie top_k z 5 do 1 dokumentu",
        "Wykrycie halucynacji (model zmysla brakujace dane)",
        inject_chaos_top_k_drop,
    ),
    (
        "chaos/sloppy-prompt",
        "Usuniecie instrukcji 'Jesli brak danych, powiedz nie wiem'",
        "Skok bledow krytycznych (1.0 -> 0.0) na pytaniach Unanswerable",
        inject_chaos_sloppy_prompt,
    ),
    (
        "chaos/heavy-reranker",
        "Dodanie bardzo powolnego cross-encodera do retrievalu",
        "Przekroczenie limitu wydajnosci P95 Latency > +250 ms",
        inject_chaos_heavy_reranker,
    ),
]


def run_chaos_evaluation_suite(
    baseline_report: Dict[str, Any],
    max_faithfulness_drop: float = 0.02,
    max_critical_regressions: int = 0,
    max_p95_latency_increase_ms: float = 250.0,
) -> ChaosEvaluationSummary:
    """Run all 4 chaos regression scenarios against baseline and compute detection rate.

    Returns:
        ChaosEvaluationSummary with 100% detection rate verification.
    """
    results: List[ChaosScenarioResult] = []

    for branch_name, injected_desc, expected_mode, injector_fn in CHAOS_SCENARIOS:
        candidate_report = injector_fn(baseline_report)
        comparison: ComparisonReport = compare_runs(baseline_report, candidate_report)
        gate_result: QualityGateResult = evaluate_gate_rules(
            comparison,
            max_faithfulness_drop=max_faithfulness_drop,
            max_critical_regressions=max_critical_regressions,
            max_p95_latency_increase_ms=max_p95_latency_increase_ms,
        )

        results.append(
            ChaosScenarioResult(
                branch_name=branch_name,
                injected_failure=injected_desc,
                expected_failure_mode=expected_mode,
                gate_passed=gate_result.passed,
                gate_blocked=not gate_result.passed,
                delta_faithfulness=comparison.delta_faithfulness,
                delta_relevance=comparison.delta_relevance,
                delta_p95_latency_ms=comparison.delta_p95_latency_ms,
                critical_regressions=comparison.critical_regressions_count,
                failure_reasons=gate_result.failure_reasons,
            )
        )

    total_scenarios = len(results)
    total_blocked = sum(1 for r in results if r.gate_blocked)
    detection_rate = (total_blocked / total_scenarios * 100.0) if total_scenarios > 0 else 0.0

    return ChaosEvaluationSummary(
        total_chaos_scenarios=total_scenarios,
        total_blocked_prs=total_blocked,
        detection_rate_pct=round(detection_rate, 2),
        scenarios=results,
    )
