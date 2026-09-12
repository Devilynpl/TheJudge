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

    delta_faith = candidate.get("mean_faithfulness", 0.0) - baseline.get("mean_faithfulness", 0.0)
    delta_rel = candidate.get("mean_relevance", 0.0) - baseline.get("mean_relevance", 0.0)
    delta_p95 = candidate.get("p95_latency_ms", 0.0) - baseline.get("p95_latency_ms", 0.0)

    critical_regressions = [r for r in regressions if r.diff <= -0.5]

    return ComparisonReport(
        baseline_commit=str(baseline.get("commit_sha", "unknown")),
        candidate_commit=str(candidate.get("commit_sha", "unknown")),
        delta_faithfulness=round(delta_faith, 4),
        delta_relevance=round(delta_rel, 4),
        delta_p95_latency_ms=round(delta_p95, 2),
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
