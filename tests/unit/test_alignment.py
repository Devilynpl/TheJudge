"""Unit tests for Judge alignment, Cohen's Kappa, and confusion matrix calculation."""

import pytest
import pandas as pd
from pathlib import Path

from judgekit.alignment import compute_judge_alignment, CalibrationMetrics


def test_compute_judge_alignment_golden_csv():
    csv_path = Path("tests/evals/calibration_results.csv")
    metrics, cm_df = compute_judge_alignment(csv_path)

    assert metrics.total_samples == 30
    assert metrics.cohen_kappa > 0.80  # Must meet gold standard
    assert metrics.is_hard_blocker_ready is True
    assert metrics.false_positives == 0  # Zero critical hallucinations allowed
    assert metrics.false_negatives == 0
    assert cm_df.shape == (3, 3)


def test_compute_judge_alignment_perfect_agreement():
    df = pd.DataFrame({
        "human_score": [1.0, 0.5, 0.0, 1.0],
        "judge_score": [1.0, 0.5, 0.0, 1.0],
    })
    metrics, _ = compute_judge_alignment(df)
    assert metrics.raw_accuracy == 1.0
    assert metrics.cohen_kappa == 1.0
    assert metrics.is_hard_blocker_ready is True


def test_compute_judge_alignment_poor_agreement():
    # Random / inverse scoring
    df = pd.DataFrame({
        "human_score": [1.0, 1.0, 0.0, 0.0],
        "judge_score": [0.0, 0.0, 1.0, 1.0],
    })
    metrics, _ = compute_judge_alignment(df)
    assert metrics.cohen_kappa < 0.40
    assert metrics.is_hard_blocker_ready is False
    assert metrics.false_positives == 2
    assert metrics.false_negatives == 2


def test_compute_judge_alignment_missing_file():
    with pytest.raises(FileNotFoundError):
        compute_judge_alignment("non_existent_calibration.csv")


def test_compute_judge_alignment_empty_dataframe():
    df = pd.DataFrame({"human_score": [], "judge_score": []})
    with pytest.raises(ValueError):
        compute_judge_alignment(df)
