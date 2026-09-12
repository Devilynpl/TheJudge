"""Quality gate enforcement engine for CI/CD pipelines.

Validates:
- Maximum allowed faithfulness drop (default: -0.02)
- Zero critical regressions (spadek >= 0.5 or 1.0 -> 0.0)
- Maximum allowed P95 latency increase SLO (default: +250 ms)
- Produces human-readable console diagnostics and strict exit codes
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union
from pydantic import BaseModel, Field

from judgekit.comparator import ComparisonReport


class QualityGateResult(BaseModel):
    """Structured evaluation of CI/CD quality gate rules."""

    passed: bool = Field(..., description="True if all hard checks passed.")
    delta_faithfulness: float
    delta_relevance: float
    delta_p95_latency_ms: float
    critical_regressions: List[Dict[str, Any]] = Field(default_factory=list)
    failure_reasons: List[str] = Field(default_factory=list)


def evaluate_gate_rules(
    diff_report_or_path: Union[ComparisonReport, Dict[str, Any], str, Path],
    max_faithfulness_drop: float = 0.02,
    max_critical_regressions: int = 0,
    max_p95_latency_increase_ms: float = 250.0,
) -> QualityGateResult:
    """Evaluate quality gate hard rules against an A/B ComparisonReport.

    Args:
        diff_report_or_path: ComparisonReport instance, raw dict, or path to JSON diff report.
        max_faithfulness_drop: Max permitted drop in faithfulness (default: 0.02).
        max_critical_regressions: Max permitted regressions with diff <= -0.5 (default: 0).
        max_p95_latency_increase_ms: Max permitted increase in P95 latency (default: 250.0 ms).

    Returns:
        QualityGateResult model.
    """
    if isinstance(diff_report_or_path, (str, Path)):
        p = Path(diff_report_or_path)
        if not p.exists():
            raise FileNotFoundError(f"Diff report file not found: {p.resolve()}")
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(diff_report_or_path, ComparisonReport):
        data = diff_report_or_path.model_dump()
    else:
        data = diff_report_or_path

    delta_faith = float(data.get("delta_faithfulness", 0.0))
    delta_rel = float(data.get("delta_relevance", 0.0))
    delta_p95 = float(data.get("delta_p95_latency_ms", 0.0))

    raw_regressions = data.get("regressions", [])
    critical_regressions = [
        r for r in raw_regressions if r.get("diff", 0.0) <= -0.5
    ]

    failure_reasons: List[str] = []

    # Rule 1: Faithfulness drop threshold
    if delta_faith < -max_faithfulness_drop:
        failure_reasons.append(
            f"Zbyt duży spadek średniej wierności ({delta_faith:+.4f} < -{max_faithfulness_drop:.2f})"
        )

    # Rule 2: Zero critical regressions
    if len(critical_regressions) > max_critical_regressions:
        failure_reasons.append(
            f"Wykryto {len(critical_regressions)} krytycznych regresji pojedynczych zapytań (limit: {max_critical_regressions})"
        )

    # Rule 3: P95 Latency SLO
    if delta_p95 > max_p95_latency_increase_ms:
        failure_reasons.append(
            f"Znaczący wzrost opóźnienia P95 (+{delta_p95:.2f} ms > +{max_p95_latency_increase_ms:.2f} ms)"
        )

    passed = len(failure_reasons) == 0

    return QualityGateResult(
        passed=passed,
        delta_faithfulness=delta_faith,
        delta_relevance=delta_rel,
        delta_p95_latency_ms=delta_p95,
        critical_regressions=critical_regressions,
        failure_reasons=failure_reasons,
    )
