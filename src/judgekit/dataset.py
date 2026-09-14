import hashlib
import json
from pathlib import Path
from typing import List, Optional, Union
from pydantic import ValidationError

from judgekit.schemas import TestCase


class DatasetValidationError(Exception):
    """Raised when one or more records in the Golden Set are malformed or invalid."""

    def __init__(self, errors: List[str]):
        super().__init__(f"Dataset validation failed with {len(errors)} error(s):\n" + "\n".join(errors))
        self.errors = errors


class DatasetIntegrityError(Exception):
    """SECURITY: Raised when the Golden Set fails cryptographic SHA-256 integrity verification."""
    pass


def load_golden_set(file_path: Union[str, Path], expected_sha256: Optional[str] = None) -> List[TestCase]:
    """Load and validate a Golden Set from a JSON Lines (.jsonl) file with integrity checks.

    Args:
        file_path: Path to the .jsonl file.
        expected_sha256: Optional expected SHA-256 hex digest to prevent dataset tampering.

    Returns:
        A list of validated TestCase instances.

    Raises:
        FileNotFoundError: If the file does not exist.
        DatasetIntegrityError: If expected_sha256 is provided and does not match the file hash.
        DatasetValidationError: If any line fails JSON parsing or Pydantic schema validation.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Golden set file not found: {path.resolve()}")

    raw_bytes = path.read_bytes()
    if expected_sha256:
        calculated_hash = hashlib.sha256(raw_bytes).hexdigest()
        if calculated_hash.lower() != expected_sha256.lower():
            raise DatasetIntegrityError(
                f"Golden Set integrity verification FAILED! Expected: {expected_sha256}, Got: {calculated_hash}. "
                "The validation dataset may have been tampered with or modified unauthorizedly."
            )

    test_cases: List[TestCase] = []
    errors: List[str] = []
    seen_ids = set()

    for line_number, raw_line in enumerate(raw_bytes.decode("utf-8").splitlines(), start=1):
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
