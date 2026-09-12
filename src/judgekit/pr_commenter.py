"""PR Markdown reporting bot for GitHub Pull Requests.

Parses diff_report.json (and optional baseline/candidate reports or gate results),
renders a high-visibility Markdown report with badges, metric tables,
and expandable regression diagnostics (CoT reasoning), and provides
helpers / CLI to post or update comments on GitHub PRs via the GitHub API.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import httpx
from pydantic import BaseModel, Field

from judgekit.gate import evaluate_gate_rules, QualityGateResult


COMMENT_HEADER_TAG = "<!-- judgekit-pr-comment -->"


def format_delta(delta: float, unit: str = "", decimals: int = 4, higher_is_better: bool = True) -> str:
    """Format delta with explicit plus sign and bold styling."""
    if delta == 0:
        val = f"{0.0:.{decimals}f}" if decimals > 0 else "0"
        return f"{val}{unit}"

    sign = "+" if delta > 0 else ""
    val_str = f"{sign}{delta:.{decimals}f}{unit}" if decimals > 0 else f"{sign}{int(delta)}{unit}"
    return f"**{val_str}**"


def generate_pr_markdown_report(
    diff_report_data_or_path: Union[Dict[str, Any], str, Path],
    baseline_data_or_path: Optional[Union[Dict[str, Any], str, Path]] = None,
    candidate_data_or_path: Optional[Union[Dict[str, Any], str, Path]] = None,
    max_faithfulness_drop: float = 0.02,
    max_critical_regressions: int = 0,
    max_p95_latency_increase_ms: float = 250.0,
) -> str:
    """Generate GitHub-flavored Markdown evaluation comment for Pull Requests.

    Args:
        diff_report_data_or_path: Dict or Path to diff_report.json.
        baseline_data_or_path: Optional baseline JSON or Dict to display absolute values.
        candidate_data_or_path: Optional candidate JSON or Dict to display absolute values.
        max_faithfulness_drop: Threshold for faithfulness.
        max_critical_regressions: Threshold for critical regressions.
        max_p95_latency_increase_ms: Threshold for latency increase.

    Returns:
        Rendered Markdown string ready to post as a PR comment.
    """
    if isinstance(diff_report_data_or_path, (str, Path)):
        p = Path(diff_report_data_or_path)
        with p.open("r", encoding="utf-8") as f:
            diff_data = json.load(f)
    else:
        diff_data = diff_report_data_or_path

    baseline_data: Dict[str, Any] = {}
    if baseline_data_or_path:
        if isinstance(baseline_data_or_path, (str, Path)):
            p = Path(baseline_data_or_path)
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    baseline_data = json.load(f)
        else:
            baseline_data = baseline_data_or_path

    candidate_data: Dict[str, Any] = {}
    if candidate_data_or_path:
        if isinstance(candidate_data_or_path, (str, Path)):
            p = Path(candidate_data_or_path)
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    candidate_data = json.load(f)
        else:
            candidate_data = candidate_data_or_path

    # Evaluate gate rules
    gate_result: QualityGateResult = evaluate_gate_rules(
        diff_data,
        max_faithfulness_drop=max_faithfulness_drop,
        max_critical_regressions=max_critical_regressions,
        max_p95_latency_increase_ms=max_p95_latency_increase_ms,
    )

    status_badge = (
        "![Status: EVAL PASSED](https://img.shields.io/badge/JudgeKit-EVAL_PASSED-success?style=for-the-badge&logo=github)"
        if gate_result.passed
        else "![Status: EVAL BLOCKED](https://img.shields.io/badge/JudgeKit-EVAL_BLOCKED-critical?style=for-the-badge&logo=github)"
    )

    delta_faith = diff_data.get("delta_faithfulness", 0.0)
    delta_rel = diff_data.get("delta_relevance", 0.0)
    delta_p95 = diff_data.get("delta_p95_latency_ms", 0.0)
    critical_reg_count = diff_data.get("critical_regressions_count", 0)

    # Resolve baseline & candidate display values
    base_faith_val = f"{baseline_data.get('mean_faithfulness', 0.0):.4f}" if baseline_data else "N/A"
    cand_faith_val = f"{candidate_data.get('mean_faithfulness', 0.0):.4f}" if candidate_data else "N/A"

    base_rel_val = f"{baseline_data.get('mean_relevance', 0.0):.4f}" if baseline_data else "N/A"
    cand_rel_val = f"{candidate_data.get('mean_relevance', 0.0):.4f}" if candidate_data else "N/A"

    base_p95_val = f"{baseline_data.get('p95_latency_ms', 0.0):.1f} ms" if baseline_data else "N/A"
    cand_p95_val = f"{candidate_data.get('p95_latency_ms', 0.0):.1f} ms" if candidate_data else "N/A"

    # Status indicators per row
    faith_status = "✅" if delta_faith >= -max_faithfulness_drop else "❌"
    rel_status = "✅" if delta_rel >= -0.05 else "❌"
    p95_status = "✅" if delta_p95 <= max_p95_latency_increase_ms else "❌"
    crit_status = "✅" if critical_reg_count <= max_critical_regressions else "❌"

    delta_faith_str = format_delta(delta_faith, decimals=4)
    delta_rel_str = format_delta(delta_rel, decimals=4)
    delta_p95_str = format_delta(delta_p95, unit=" ms", decimals=1)
    delta_crit_str = f"+{critical_reg_count}" if critical_reg_count > 0 else "0"
    if critical_reg_count > 0:
        delta_crit_str = f"**{delta_crit_str}**"

    lines = [
        COMMENT_HEADER_TAG,
        "## ⚖️ JudgeKit Evaluation Report",
        "",
        f"{status_badge}",
        "",
        "| Status | Metric | Baseline (`main`) | Candidate (PR) | Delta | Threshold |",
        "| :---: | :--- | :---: | :---: | :---: | :---: |",
        f"| {faith_status} | **Faithfulness** | {base_faith_val} | {cand_faith_val} | {delta_faith_str} | $\\ge -{max_faithfulness_drop:.2f}$ |",
        f"| {rel_status} | **Relevance** | {base_rel_val} | {cand_rel_val} | {delta_rel_str} | $\\ge -0.05$ |",
        f"| {p95_status} | **P95 Latency** | {base_p95_val} | {cand_p95_val} | {delta_p95_str} | $\\le +{max_p95_latency_increase_ms:.0f}\\text{{ ms}}$ |",
        f"| {crit_status} | **Critical Regressions** | 0 | {critical_reg_count} | {delta_crit_str} | **{max_critical_regressions}** |",
        "",
    ]

    regressions: List[Dict[str, Any]] = diff_data.get("regressions", [])
    if regressions:
        lines.append(f"<details>")
        lines.append(f"<summary><b>🔍 Zidentyfikowane regresje jakościowe ({len(regressions)} przypadków)</b></summary>")
        lines.append("")
        for reg in regressions:
            t_id = reg.get("test_id", "unknown")
            b_sc = reg.get("baseline_score", 0.0)
            c_sc = reg.get("candidate_score", 0.0)
            metric_name = reg.get("metric", "faithfulness")
            reason = reg.get("reason", "Brak uzasadnienia sędziego.")
            is_crit = " ⚠️ **[KRYTYCZNA]**" if reg.get("diff", 0.0) <= -0.5 else ""

            lines.append(f"- **Case ID:** `{t_id}`{is_crit}")
            lines.append(f"  - **Metryka:** `{metric_name}`")
            lines.append(f"  - **Spadek noty:** z `{b_sc:.2f}` do `{c_sc:.2f}` (diff: `{reg.get('diff', 0.0):+.2f}`)")
            lines.append(f"  - **Uzasadnienie sędziego (CoT):** {reason}")
            lines.append("")
        lines.append("</details>")
        lines.append("")
    else:
        lines.append("> 🎯 **Brak regresji jakościowych** — wszystkie odpowiedzi kandydata utrzymały lub poprawiły noty referencyjne.")
        lines.append("")

    if not gate_result.passed:
        lines.append("### 🚫 Powody odrzucenia przez Quality Gate:")
        for r in gate_result.failure_reasons:
            lines.append(f"- ❌ {r}")
        lines.append("")

    return "\n".join(lines)


def post_or_update_pr_comment(
    repo: str,
    pr_number: int,
    body: str,
    github_token: str,
    api_url: str = "https://api.github.com",
) -> Dict[str, Any]:
    """Find existing JudgeKit PR comment and update it, or create a new comment.

    Args:
        repo: Repository format 'owner/repo'.
        pr_number: GitHub Pull Request number.
        body: Markdown body of comment.
        github_token: Personal access token or GitHub Actions GITHUB_TOKEN.
        api_url: GitHub API base URL (defaults to https://api.github.com).

    Returns:
        JSON response from GitHub API.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {github_token}",
        "User-Agent": "JudgeKit-PR-Commenter",
    }

    with httpx.Client(base_url=api_url, headers=headers, timeout=20.0) as client:
        # 1. Fetch existing comments on PR
        url = f"/repos/{repo}/issues/{pr_number}/comments"
        resp = client.get(url)
        resp.raise_for_status()
        comments = resp.json()

        existing_comment_id = None
        for comment in comments:
            if COMMENT_HEADER_TAG in comment.get("body", ""):
                existing_comment_id = comment["id"]
                break

        # 2. Update or Create
        if existing_comment_id:
            update_url = f"/repos/{repo}/issues/comments/{existing_comment_id}"
            patch_resp = client.patch(update_url, json={"body": body})
            patch_resp.raise_for_status()
            return patch_resp.json()
        else:
            post_resp = client.post(url, json={"body": body})
            post_resp.raise_for_status()
            return post_resp.json()

