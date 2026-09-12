"""CLI tool to evaluate Judge alignment with Human scores using Cohen's Kappa."""

import argparse
import sys
from pathlib import Path

from judgekit.alignment import compute_judge_alignment


def main():
    parser = argparse.ArgumentParser(
        description="JudgeKit: Validate Judge alignment against human expert ratings using Cohen's Kappa."
    )
    parser.add_argument(
        "--data",
        type=str,
        default="tests/evals/calibration_results.csv",
        help="Path to CSV calibration file with human and judge scores.",
    )
    parser.add_argument(
        "--min-kappa",
        type=float,
        default=0.80,
        help="Minimum required Cohen's Kappa coefficient (default: 0.80).",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"[ERROR] Calibration file not found: {data_path.resolve()}", file=sys.stderr)
        sys.exit(1)

    metrics, cm_df = compute_judge_alignment(data_path)

    print("=" * 60)
    print("JUDGEKIT: RAPORT KALIBRACJI SEDZIEGO (HUMAN-IN-THE-LOOP)")
    print("=" * 60)
    print(f"Liczba próbek testowych:       {metrics.total_samples}")
    print(f"Dokładność bezwzględna (Po):   {metrics.raw_accuracy * 100:.2f}%")
    print(f"Współczynnik Cohen's Kappa:    {metrics.cohen_kappa:.4f}")
    print(f"Interpretacja wyniku:          {metrics.interpretation}")
    print(f"Krytyczne False Positives (0->1): {metrics.false_positives}")
    print(f"False Negatives (1->0):        {metrics.false_negatives}")
    print("-" * 60)
    print("Macierz Pomyłek (Confusion Matrix):")
    print(cm_df)
    print("=" * 60)

    if metrics.cohen_kappa < args.min_kappa:
        print(
            f"\n[FAIL] Sędzia NIE osiągnął wymaganego progu kappa >= {args.min_kappa:.2f} (Aktualny: {metrics.cohen_kappa:.4f}).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"\n[SUCCESS] Sędzia osiągnął złoty standard jakości (kappa: {metrics.cohen_kappa:.4f} >= {args.min_kappa:.2f})."
    )
    print("Sędzia jest gotowy do pełnienia roli twardej bramki (Hard Blocker) w CI/CD.")
    sys.exit(0)


if __name__ == "__main__":
    main()
