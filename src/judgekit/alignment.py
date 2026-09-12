"""Validation and alignment tools for measuring Judge inter-rater agreement with human experts.

Implements:
- Cohen's Kappa (kappa) statistical calculation
- Confusion Matrix extraction across discrete thresholds (0.0, 0.5, 1.0)
- Human vs Judge calibration runner and analysis
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.metrics import cohen_kappa_score, confusion_matrix


class CalibrationMetrics(BaseModel):
    """Statistical summary of Human-in-the-loop Judge validation."""

    total_samples: int = Field(..., description="Total number of evaluated samples.")
    raw_accuracy: float = Field(..., description="Observed percentage agreement (Po).")
    cohen_kappa: float = Field(..., description="Cohen's Kappa coefficient (inter-rater reliability).")
    interpretation: str = Field(..., description="Qualitative interpretation of agreement.")
    is_hard_blocker_ready: bool = Field(
        ...,
        description="True if Cohen's Kappa > 0.80 (ready for hard blocking in CI).",
    )
    confusion_matrix_dict: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Confusion matrix breakdown: Human vs Judge.",
    )
    false_positives: int = Field(
        default=0,
        description="Number of critical false positives (Human: 0.0, Judge: 1.0).",
    )
    false_negatives: int = Field(
        default=0,
        description="Number of false negatives (Human: 1.0, Judge: 0.0).",
    )


def compute_judge_alignment(
    df_or_path: Union[pd.DataFrame, str, Path],
    human_col: str = "human_score",
    judge_col: str = "judge_score",
    labels: Optional[List[str]] = None,
) -> Tuple[CalibrationMetrics, pd.DataFrame]:
    """Compute Cohen's Kappa, Confusion Matrix, and Error Breakdown between Human and Judge scores.

    Args:
        df_or_path: DataFrame or path to CSV file.
        human_col: Column containing human scores (e.g. 0.0, 0.5, 1.0).
        judge_col: Column containing judge scores (e.g. 0.0, 0.5, 1.0).
        labels: Discrete score labels (defaults to ['0.0', '0.5', '1.0']).

    Returns:
        Tuple of (CalibrationMetrics, confusion_matrix_DataFrame).
    """
    if labels is None:
        labels = ["0.0", "0.5", "1.0"]

    if isinstance(df_or_path, (str, Path)):
        path = Path(df_or_path)
        if not path.exists():
            raise FileNotFoundError(f"Calibration data not found: {path.resolve()}")
        df = pd.read_csv(path)
    else:
        df = df_or_path.copy()

    # Normalize scores to string representation matching labels
    df[human_col] = df[human_col].astype(float).round(1).astype(str)
    df[judge_col] = df[judge_col].astype(float).round(1).astype(str)

    human = df[human_col]
    judge = df[judge_col]

    total_samples = len(df)
    if total_samples == 0:
        raise ValueError("Calibration dataset is empty.")

    # Calculate metrics
    raw_acc = float((human == judge).mean())
    kappa = float(cohen_kappa_score(human, judge, labels=labels))

    # Confusion matrix
    cm = confusion_matrix(human, judge, labels=labels)
    cm_df = pd.DataFrame(
        cm,
        index=[f"Human {lbl}" for lbl in labels],
        columns=[f"Judge {lbl}" for lbl in labels],
    )

    # Convert confusion matrix to dict
    cm_dict = {
        row_label: {col_label: int(val) for col_label, val in row_data.items()}
        for row_label, row_data in cm_df.to_dict(orient="index").items()
    }

    # Error analysis:
    # False Positive (Human: 0.0, Judge: 1.0)
    fp_mask = (df[human_col] == "0.0") & (df[judge_col] == "1.0")
    # False Negative (Human: 1.0, Judge: 0.0)
    fn_mask = (df[human_col] == "1.0") & (df[judge_col] == "0.0")

    # Interpretation
    if kappa < 0.40:
        interp = "Słaba / losowa zgodność (Sędzia bezużyteczny)"
        hard_ready = False
    elif kappa <= 0.60:
        interp = "Umiarkowana zgodność (Za dużo niejednoznaczności)"
        hard_ready = False
    elif kappa <= 0.80:
        interp = "Dobra / Akceptowalna (Dopuszczalny jako warning w CI)"
        hard_ready = False
    else:
        interp = "Bardzo wysoka zgodność (Złoty standard CI - Hard Blocker)"
        hard_ready = True

    metrics = CalibrationMetrics(
        total_samples=total_samples,
        raw_accuracy=round(raw_acc, 4),
        cohen_kappa=round(kappa, 4),
        interpretation=interp,
        is_hard_blocker_ready=hard_ready,
        confusion_matrix_dict=cm_dict,
        false_positives=int(fp_mask.sum()),
        false_negatives=int(fn_mask.sum()),
    )

    return metrics, cm_df
