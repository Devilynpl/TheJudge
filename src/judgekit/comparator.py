"""A/B Comparator and regression detection engine (Baseline vs Candidate).

Computes:
- Global Delta (mean faithfulness, relevance, P95 latency)
- Pointwise regressions and improvements per test case
- Critical regression flags (score drop >= 0.5 or 1.0 -> 0.0)
- Net regression rate
- JSON diff report generation
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class CaseDiff(BaseModel):
    """Detailed differential evaluation for a single test case."""

    test_id: str = Field(..., description="ID of the test case.")
    metric: str = Field(default="faithfulness", description="Metric name (e.g. faithfulness, relevance).")
    baseline_score: float = Field(..., description="Score in baseline run.")
    candidate_score: float = Field(..., description="Score in candidate run.")
    diff: float = Field(..., description="Candidate score minus baseline score.")
    reason: str = Field(default="", description="Reasoning provided by the candidate judge.")
    query: Optional[str] = Field(default=None, description="Original query if present.")


class ComparisonReport(BaseModel):
    """Aggregated A/B comparison report between baseline and candidate runs."""

    baseline_commit: str = Field(default="unknown", description="Baseline commit SHA.")
    candidate_commit: str = Field(default="unknown", description="Candidate commit SHA.")
    delta_faithfulness: float = Field(..., description="Candidate mean faithfulness minus baseline.")
    delta_relevance: float = Field(..., description="Candidate mean relevance minus baseline.")
    delta_p95_latency_ms: float = Field(..., description="Candidate P95 latency minus baseline.")
    # RAGAS metrics deltas
    delta_ragas_faithfulness: Optional[float] = Field(default=None, description="Candidate Ragas faithfulness minus baseline.")
    delta_ragas_answer_relevancy: Optional[float] = Field(default=None, description="Candidate Ragas answer relevancy minus baseline.")
    delta_ragas_context_precision: Optional[float] = Field(default=None, description="Candidate Ragas context precision minus baseline.")
    delta_ragas_context_recall: Optional[float] = Field(default=None, description="Candidate Ragas context recall minus baseline.")
    regressions: List[CaseDiff] = Field(default_factory=list, description="Cases where score degraded.")
    improvements: List[CaseDiff] = Field(default_factory=list, description="Cases where score improved.")
    critical_regressions_count: int = Field(default=0, description="Count of regressions with drop >= 0.5.")
    total_compared_cases: int = Field(default=0, description="Number of intersecting cases compared.")


def compare_runs(
    baseline_data_or_path: Union[Dict[str, Any], str, Path],
    candidate_data_or_path: Union[Dict[str, Any], str, Path],
) -> ComparisonReport:
    """Compare baseline evaluation results against candidate evaluation results.

    Args:
        baseline_data_or_path: Dict or Path to baseline JSON report.
        candidate_data_or_path: Dict or Path to candidate JSON report.

    Returns:
        ComparisonReport model containing deltas, regressions, and improvements.
    """
    if isinstance(baseline_data_or_path, (str, Path)):
        p_base = Path(baseline_data_or_path)
        if not p_base.exists():
            raise FileNotFoundError(f"Baseline file not found: {p_base.resolve()}")
        with p_base.open("r", encoding="utf-8") as f:
            baseline = json.load(f)
    else:
        baseline = baseline_data_or_path

    if isinstance(candidate_data_or_path, (str, Path)):
        p_cand = Path(candidate_data_or_path)
        if not p_cand.exists():
            raise FileNotFoundError(f"Candidate file not found: {p_cand.resolve()}")
        with p_cand.open("r", encoding="utf-8") as f:
            candidate = json.load(f)
    else:
        candidate = candidate_data_or_path

    b_cases = {c["test_id"]: c for c in baseline.get("cases", [])}
    c_cases = {c["test_id"]: c for c in candidate.get("cases", [])}

    regressions: List[CaseDiff] = []
    improvements: List[CaseDiff] = []
    compared_count = 0

    for test_id, c_case in c_cases.items():
        if test_id not in b_cases:
            continue

        compared_count += 1
        b_case = b_cases[test_id]
        diff_faith = round(c_case["faithfulness_score"] - b_case["faithfulness_score"], 2)

        if diff_faith < 0:
            regressions.append(
                CaseDiff(
                    test_id=test_id,
                    metric="faithfulness",
                    baseline_score=b_case["faithfulness_score"],
                    candidate_score=c_case["faithfulness_score"],
                    diff=diff_faith,
                    reason=c_case.get("faithfulness_reasoning", "Brak uzasadnienia"),
                )
            )
        elif diff_faith > 0:
            improvements.append(
                CaseDiff(
                    test_id=test_id,
                    metric="faithfulness",
                    baseline_score=b_case["faithfulness_score"],
                    candidate_score=c_case["faithfulness_score"],
                    diff=diff_faith,
                    reason=c_case.get("faithfulness_reasoning", ""),
                )
            )

        # Check RAGAS faithfulness diff if present
        b_rf = b_case.get("ragas_faithfulness")
        c_rf = c_case.get("ragas_faithfulness")
        if b_rf is not None and c_rf is not None:
            diff_rf = round(c_rf - b_rf, 2)
            if diff_rf < 0:
                reason = "Spadek wierności RAGAS"
                if isinstance(c_case.get("ragas_reasoning"), dict):
                    reason = c_case["ragas_reasoning"].get("faithfulness", reason)
                regressions.append(
                    CaseDiff(
                        test_id=test_id,
                        metric="ragas_faithfulness",
                        baseline_score=b_rf,
                        candidate_score=c_rf,
                        diff=diff_rf,
                        reason=reason,
                    )
                )

    delta_faith = candidate.get("mean_faithfulness", 0.0) - baseline.get("mean_faithfulness", 0.0)
    delta_rel = candidate.get("mean_relevance", 0.0) - baseline.get("mean_relevance", 0.0)
    delta_p95 = candidate.get("p95_latency_ms", 0.0) - baseline.get("p95_latency_ms", 0.0)

    # Calculate RAGAS global deltas
    delta_ragas_faith = None
    if candidate.get("ragas_mean_faithfulness") is not None and baseline.get("ragas_mean_faithfulness") is not None:
        delta_ragas_faith = round(candidate["ragas_mean_faithfulness"] - baseline["ragas_mean_faithfulness"], 4)

    delta_ragas_rel = None
    if candidate.get("ragas_mean_answer_relevancy") is not None and baseline.get("ragas_mean_answer_relevancy") is not None:
        delta_ragas_rel = round(candidate["ragas_mean_answer_relevancy"] - baseline["ragas_mean_answer_relevancy"], 4)

    delta_ragas_prec = None
    if candidate.get("ragas_mean_context_precision") is not None and baseline.get("ragas_mean_context_precision") is not None:
        delta_ragas_prec = round(candidate["ragas_mean_context_precision"] - baseline["ragas_mean_context_precision"], 4)

    delta_ragas_rec = None
    if candidate.get("ragas_mean_context_recall") is not None and baseline.get("ragas_mean_context_recall") is not None:
        delta_ragas_rec = round(candidate["ragas_mean_context_recall"] - baseline["ragas_mean_context_recall"], 4)

    critical_regressions = [r for r in regressions if r.diff <= -0.5]

    return ComparisonReport(
        baseline_commit=str(baseline.get("commit_sha", "unknown")),
        candidate_commit=str(candidate.get("commit_sha", "unknown")),
        delta_faithfulness=round(delta_faith, 4),
        delta_relevance=round(delta_rel, 4),
        delta_p95_latency_ms=round(delta_p95, 2),
        delta_ragas_faithfulness=delta_ragas_faith,
        delta_ragas_answer_relevancy=delta_ragas_rel,
        delta_ragas_context_precision=delta_ragas_prec,
        delta_ragas_context_recall=delta_ragas_rec,
        regressions=regressions,
        improvements=improvements,
        critical_regressions_count=len(critical_regressions),
        total_compared_cases=compared_count,
    )


def export_diff_report(report: ComparisonReport, output_path: Union[str, Path]) -> Path:
    """Save comparison report to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)
    return path
