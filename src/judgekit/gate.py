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
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from judgekit.comparator import ComparisonReport
from judgekit.schemas import GateConfig


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


def evaluate_absolute_gate_rules(
    summary_data_or_path: Union[Dict[str, Any], str, Path],
    gate_config: Optional[Union[Dict[str, Any], GateConfig]] = None,
) -> QualityGateResult:
    """Evaluate absolute quality gate rules directly against a RunSummary report.

    Checks:
    - Minimum Faithfulness (e.g. >= 0.95)
    - Minimum Citation Precision (e.g. >= 0.90)
    - Deterministic Refusal (e.g. 100% on out-of-domain)
    - Zero Hallucination on Stealth Entities (e.g. 100% UNVERIFIABLE_COMPANY)
    - Rubric Score (e.g. >= 0.83)
    - Budget Compliance (100% within steps/cost)
    - P95 Latency SLO threshold
    """
    if isinstance(summary_data_or_path, (str, Path)):
        p = Path(summary_data_or_path)
        if not p.exists():
            raise FileNotFoundError(f"Run summary file not found: {p.resolve()}")
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    elif hasattr(summary_data_or_path, "model_dump"):
        data = summary_data_or_path.model_dump()
    else:
        data = summary_data_or_path

    if gate_config is None:
        cfg = GateConfig()
    elif isinstance(gate_config, GateConfig):
        cfg = gate_config
    elif isinstance(gate_config, (str, Path)):
        with Path(gate_config).open("r", encoding="utf-8") as f:
            cfg = GateConfig.model_validate(json.load(f))
    else:
        cfg = GateConfig.model_validate(gate_config)

    failure_reasons: List[str] = []

    mean_faith = float(data.get("mean_faithfulness", 0.0))
    p95_lat = float(data.get("p95_latency_ms", 0.0))
    crit_failures = int(data.get("critical_failures", 0))

    # 1. Faithfulness
    if mean_faith < cfg.min_faithfulness:
        failure_reasons.append(
            f"Wierność (Faithfulness) {mean_faith:.4f} poniżej progu {cfg.min_faithfulness:.4f}"
        )

    # 2. Critical failures (faithfulness == 0.0)
    if crit_failures > cfg.max_critical_regressions:
        failure_reasons.append(
            f"Wykryto {crit_failures} krytycznych błędów faktograficznych (faithfulness=0.0)"
        )

    # 3. Citation Precision
    cit_prec = data.get("mean_citation_precision")
    if cit_prec is not None and cit_prec < cfg.min_citation_precision:
        failure_reasons.append(
            f"Precyzja cytowań {cit_prec:.4f} poniżej wymaganego progu {cfg.min_citation_precision:.4f}"
        )

    # 4. Deterministic Refusal
    refusal_acc = data.get("refusal_accuracy")
    if cfg.require_deterministic_refusal and refusal_acc is not None and refusal_acc < 1.0:
        failure_reasons.append(
            f"Skuteczność deterministycznej odmowy {refusal_acc*100:.1f}% poniżej 100%"
        )

    # 5. Rubric Score
    rubric_val = data.get("mean_rubric_score")
    if rubric_val is not None and rubric_val < cfg.min_rubric_score:
        failure_reasons.append(
            f"Zgodność z rubryką kryteriów {rubric_val:.4f} poniżej progu {cfg.min_rubric_score:.4f}"
        )

    # 6. Stealth Zero-Hallucination
    stealth_acc = data.get("stealth_accuracy")
    if cfg.require_stealth_zero_hallucination and stealth_acc is not None and stealth_acc < 1.0:
        failure_reasons.append(
            f"Wykryto halucynacje na firmach stealth! Skuteczność: {stealth_acc*100:.1f}% (wymagane 100%)"
        )

    # 7. Budget compliance
    budget_rate = data.get("budget_compliance_rate")
    if budget_rate is not None and budget_rate < 1.0:
        failure_reasons.append(
            f"Naruszenie twardego limitu budżetu! Zgodność: {budget_rate*100:.1f}% (wymagane 100%)"
        )

    # 8. P95 Latency absolute SLO
    if p95_lat > cfg.max_p95_latency_ms:
        failure_reasons.append(
            f"Opóźnienie P95 {p95_lat:.1f} ms przekracza próg SLO {cfg.max_p95_latency_ms:.1f} ms"
        )

    return QualityGateResult(
        passed=len(failure_reasons) == 0,
        delta_faithfulness=mean_faith,
        delta_relevance=float(data.get("mean_relevance", 0.0)),
        delta_p95_latency_ms=p95_lat,
        critical_regressions=[],
        failure_reasons=failure_reasons,
    )

