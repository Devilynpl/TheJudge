"""Unit tests for Golden Set dataset loading and validation."""

import pytest
from pathlib import Path

from judgekit.dataset import load_golden_set, save_golden_set, DatasetValidationError
from judgekit.schemas import TestCase


def test_load_golden_set_official_dataset():
    data_path = Path("tests/evals/data/golden_set.jsonl")
    dataset = load_golden_set(data_path)

    assert len(dataset) == 20
    categories = {tc.category for tc in dataset}
    assert "factual" in categories
    assert "unanswerable" in categories
    assert "multi_hop" in categories
    assert "edge_case" in categories
    assert "jailbreak" in categories

    # Verify ID uniqueness
    ids = [tc.id for tc in dataset]
    assert len(ids) == len(set(ids))


def test_load_golden_set_missing_file():
    with pytest.raises(FileNotFoundError):
        load_golden_set("non_existent_golden_set.jsonl")


def test_load_golden_set_invalid_json(tmp_path):
    bad_file = tmp_path / "bad.jsonl"
    bad_file.write_text("{\"id\": \"1\", invalid json}\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_set(bad_file)
    assert "Invalid JSON" in str(excinfo.value)


def test_load_golden_set_duplicate_ids(tmp_path):
    dup_file = tmp_path / "duplicate.jsonl"
    tc1 = '{"id": "eval-001", "category": "factual", "query": "Q1?", "expected_behavior": "B1"}\n'
    tc2 = '{"id": "eval-001", "category": "factual", "query": "Q2?", "expected_behavior": "B2"}\n'
    dup_file.write_text(tc1 + tc2, encoding="utf-8")

    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_set(dup_file)
    assert "Duplicate test case ID" in str(excinfo.value)


def test_save_and_reload_golden_set(tmp_path):
    test_cases = [
        TestCase(
            id="test-01",
            category="factual",
            query="Test query?",
            expected_behavior="Expected response.",
            reference_answer="Answer.",
            reference_contexts=["Context 1"],
        ),
        TestCase(
            id="test-02",
            category="unanswerable",
            query="Unknown query?",
            expected_behavior="Refuse gracefully.",
        ),
    ]

    out_file = tmp_path / "exported.jsonl"
    save_golden_set(test_cases, out_file)
    reloaded = load_golden_set(out_file)

    assert len(reloaded) == 2
    assert reloaded[0].id == "test-01"
    assert reloaded[1].expected_behavior == "Refuse gracefully."
