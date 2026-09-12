"""CLI tool to execute Chaos Engineering evaluation on RAG regressions."""

import argparse
import json
import sys
from pathlib import Path

# Ensure UTF-8 stdout on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from judgekit.chaos_eval import run_chaos_evaluation_suite


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JudgeKit Chaos Evaluation Harness (RAG Regressions Verification)."
    )
    parser.add_argument(
        "--baseline",
        default="artifacts/baseline.json",
        help="Path to baseline evaluation JSON (default: artifacts/baseline.json).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to export chaos evaluation summary JSON.",
    )

    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"Error: Baseline file not found: {baseline_path.resolve()}", file=sys.stderr)
        sys.exit(1)

    with baseline_path.open("r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    print("================================================================================")
    print(" 💥 JudgeKit Chaos Eval: Wstrzykiwanie Syntetycznych Regresji RAG")
    print("================================================================================")

    summary = run_chaos_evaluation_suite(baseline_data)

    for sc in summary.scenarios:
        icon = "🛑 [ZABLOKOWANY PR]" if sc.gate_blocked else "⚠️ [PRZEPUSZCZONY]"
        print(f"\nBranch: {sc.branch_name} -> {icon}")
        print(f"  * Wstrzyknięta zmiana: {sc.injected_failure}")
        print(f"  * Oczekiwany objaw:   {sc.expected_failure_mode}")
        print(f"  * Δ Faithfulness:     {sc.delta_faithfulness:+.4f}")
        print(f"  * Δ P95 Latency:      {sc.delta_p95_latency_ms:+.1f} ms")
        print(f"  * Regresje krytyczne: {sc.critical_regressions}")
        print(f"  * Powody odrzucenia:  {'; '.join(sc.failure_reasons)}")

    print("\n--------------------------------------------------------------------------------")
    print(f" Wynik Końcowy Chaos Engineering:")
    print(f"   Liczba scenariuszy awaryjnych : {summary.total_chaos_scenarios}")
    print(f"   Liczba zablokowanych PR-ów    : {summary.total_blocked_prs}")
    print(f"   Wskaźnik Wykrywalności (RDR)  : {summary.detection_rate_pct:.1f}%")
    print("--------------------------------------------------------------------------------")

    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"Raport Chaos Eval zapisany do: {out_p.resolve()}")

    if summary.detection_rate_pct < 100.0:
        print("\n❌ BŁĄD: Quality Gate nie wykrył wszystkich zdefiniowanych awarii!", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n✅ SUKCES: 100% zdefiniowanych awarii RAG zostało zablokowanych przez Quality Gate.")


if __name__ == "__main__":
    main()
