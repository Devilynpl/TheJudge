"""Dataset loader and validator for JudgeKit Golden Sets (JSONL format)."""

import json
from pathlib import Path
from typing import List, Union
from pydantic import ValidationError

from judgekit.schemas import TestCase


class DatasetValidationError(Exception):
    """Raised when one or more records in the Golden Set are malformed or invalid."""

    def __init__(self, errors: List[str]):
        super().__init__(f"Dataset validation failed with {len(errors)} error(s):\n" + "\n".join(errors))
        self.errors = errors


def load_golden_set(file_path: Union[str, Path]) -> List[TestCase]:
    """Load and validate a Golden Set from a JSON Lines (.jsonl) file.

    Args:
        file_path: Path to the .jsonl file.

    Returns:
        A list of validated TestCase instances.

    Raises:
        FileNotFoundError: If the file does not exist.
        DatasetValidationError: If any line fails JSON parsing or Pydantic schema validation.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Golden set file not found: {path.resolve()}")

    test_cases: List[TestCase] = []
    errors: List[str] = []
    seen_ids = set()

    with path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as err:
                errors.append(f"Line {line_number}: Invalid JSON - {err.msg}")
                continue

            try:
                # Support DocGround format (question, is_answerable, expected_answer_keywords)
                if "query" not in data and "question" in data:
                    data["query"] = data["question"]
                if "expected_behavior" not in data:
                    is_ans = data.get("is_answerable", True)
                    if not is_ans:
                        data["expected_behavior"] = "Refuse to answer due to missing context."
                    else:
                        keywords = ", ".join(data.get("expected_answer_keywords", []))
                        data["expected_behavior"] = f"Answer factually using document context with keywords: {keywords}"

                test_case = TestCase.model_validate(data)
                if test_case.id in seen_ids:
                    errors.append(f"Line {line_number}: Duplicate test case ID '{test_case.id}'")
                else:
                    seen_ids.add(test_case.id)
                    test_cases.append(test_case)
            except ValidationError as err:
                errors.append(f"Line {line_number} (id: {data.get('id', 'UNKNOWN')}): Schema error - {err}")

    if errors:
        raise DatasetValidationError(errors)

    return test_cases


def save_golden_set(test_cases: List[TestCase], file_path: Union[str, Path]) -> None:
    """Save a list of TestCase instances to a JSON Lines (.jsonl) file.

    Args:
        test_cases: List of TestCase models.
        file_path: Destination path.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for tc in test_cases:
            f.write(tc.model_dump_json() + "\n")
