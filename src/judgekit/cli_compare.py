"""CLI interface for JudgeKit A/B regression detection and performance comparator."""

import argparse
import sys
from pathlib import Path

from judgekit.comparator import compare_runs, export_diff_report


def main():
    parser = argparse.ArgumentParser(
        description="JudgeKit A/B Comparator: Detect pointwise regressions and latency delta between Baseline and Candidate."
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default="artifacts/baseline.json",
        help="Path to baseline evaluation JSON report.",
    )
    parser.add_argument(
        "--candidate",
        type=str,
        default="artifacts/candidate.json",
        help="Path to candidate evaluation JSON report.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/diff_report.json",
        help="Output destination path for diff report JSON.",
    )
    parser.add_argument(
        "--max-regressions",
        type=int,
        default=0,
        help="Maximum allowed critical regressions (default: 0).",
    )
    parser.add_argument(
        "--max-p95-latency-increase-ms",
        type=float,
        default=200.0,
        help="Maximum allowed increase in P95 latency in ms (default: 200.0 ms).",
    )
    parser.add_argument(
        "--max-faithfulness-drop",
        type=float,
        default=0.02,
        help="Maximum allowed drop in mean faithfulness (default: 0.02).",
    )
    parser.add_argument(
        "--max-ragas-faith-drop",
        type=float,
        default=None,
        help="Optional maximum allowed drop in mean RAGAS faithfulness.",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)

    if not baseline_path.exists():
        print(f"[ERROR] Baseline file not found: {baseline_path.resolve()}", file=sys.stderr)
        sys.exit(1)
    if not candidate_path.exists():
        print(f"[ERROR] Candidate file not found: {candidate_path.resolve()}", file=sys.stderr)
        sys.exit(1)

    report = compare_runs(baseline_path, candidate_path)
    out_path = export_diff_report(report, args.output)

    print("=" * 60)
    print("JUDGEKIT: RAPORT POROWNAWCZY A/B (BASELINE vs CANDIDATE)")
    print("=" * 60)
    print(f"Baseline Commit:       {report.baseline_commit}")
    print(f"Candidate Commit:      {report.candidate_commit}")
    print(f"Porownane przypadki:   {report.total_compared_cases}")
    print(f"Delta Faithfulness:    {report.delta_faithfulness:+.4f}")
    print(f"Delta Relevance:       {report.delta_relevance:+.4f}")
    if report.delta_ragas_faithfulness is not None:
        print(f"Delta RAGAS Faith:     {report.delta_ragas_faithfulness:+.4f}")
    if report.delta_ragas_answer_relevancy is not None:
        print(f"Delta RAGAS Relevancy: {report.delta_ragas_answer_relevancy:+.4f}")
    if report.delta_ragas_context_precision is not None:
        print(f"Delta RAGAS Precision: {report.delta_ragas_context_precision:+.4f}")
    if report.delta_ragas_context_recall is not None:
        print(f"Delta RAGAS Recall:    {report.delta_ragas_context_recall:+.4f}")
    print(f"Delta P95 Latency:     {report.delta_p95_latency_ms:+.2f} ms")
    print(f"Wykryte poprawy (+):   {len(report.improvements)}")
    print(f"Wykryte regresje (-):  {len(report.regressions)}")
    print(f"Krytyczne regresje:    {report.critical_regressions_count}")
    print("-" * 60)

    if report.regressions:
        print("SZCZEGOLY REGRESJI:")
        for reg in report.regressions:
            print(
                f"  - Case [{reg.test_id}] ({reg.metric}): {reg.baseline_score} -> {reg.candidate_score} (diff: {reg.diff}). Uzasadnienie: {reg.reason}"
            )
        print("-" * 60)

    # Verification of threshold constraints
    failed = False
    if report.delta_faithfulness < -args.max_faithfulness_drop:
        print(
            f"[FAIL] Spadek sredniej wiernosci ({report.delta_faithfulness:+.4f}) przekroczyl limit (-{args.max_faithfulness_drop}).",
            file=sys.stderr,
        )
        failed = True

    if args.max_ragas_faith_drop is not None and report.delta_ragas_faithfulness is not None:
        if report.delta_ragas_faithfulness < -args.max_ragas_faith_drop:
            print(
                f"[FAIL] Spadek sredniej wiernosci RAGAS ({report.delta_ragas_faithfulness:+.4f}) przekroczyl limit (-{args.max_ragas_faith_drop}).",
                file=sys.stderr,
            )
            failed = True

    if report.critical_regressions_count > args.max_regressions:
        print(
            f"[FAIL] Liczba krytycznych regresji ({report.critical_regressions_count}) przekracza dopuszczalny limit ({args.max_regressions})!",
            file=sys.stderr,
        )
        failed = True

    if report.delta_p95_latency_ms > args.max_p95_latency_increase_ms:
        print(
            f"[FAIL] Wzrost opoznienia P95 (+{report.delta_p95_latency_ms:.2f} ms) przekroczyl SLO (+{args.max_p95_latency_increase_ms:.2f} ms)!",
            file=sys.stderr,
        )
        failed = True

    print(f"Raport diff zapisano w: {out_path.resolve()}")

    if failed:
        print("\n>>> BLOKADA: Wykryto niedopuszczalna regresje! Proces konczy sie kodem bledu. <<<", file=sys.stderr)
        sys.exit(1)

    print("\n>>> SUKCES: Kandydat spelnia wszystkie kryteria jakosciowe i wydajnosciowe. <<<")
    sys.exit(0)


if __name__ == "__main__":
    main()
