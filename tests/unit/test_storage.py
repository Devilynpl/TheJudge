"""Unit tests for SQLite storage and ingestion service."""

import sqlite3
from pathlib import Path
import pytest

from judgekit.storage import init_db
from judgekit.ingest_run import ingest_evaluation_run


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_eval_history.db"


def test_init_db(temp_db: Path):
    db_path = init_db(temp_db)
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "runs" in tables
        assert "test_results" in tables


def test_ingest_evaluation_run(temp_db: Path):
    mock_report = {
        "commit_sha": "testsha123",
        "branch": "main",
        "mean_faithfulness": 0.95,
        "mean_relevance": 0.90,
        "p95_latency_ms": 150.5,
        "total_cost_usd": 0.0012,
        "cases": [
            {
                "test_id": "eval-001",
                "query": "Jaki jest czas gwarancji?",
                "generated_answer": "Okres gwarancji wynosi 24 miesiace.",
                "faithfulness_score": 1.0,
                "faithfulness_reasoning": "Zgodne z kontekstem.",
                "relevance_score": 1.0,
                "relevance_reasoning": "Odpowiedz wprost na pytanie.",
                "latency_ms": 120.0,
            },
            {
                "test_id": "eval-002",
                "query": "Czy mozna zwrocic towar?",
                "generated_answer": "Nie, brak zwrotow.",
                "faithfulness_score": 0.0,
                "faithfulness_reasoning": "Kontekst mowi o 14 dniach na zwrot.",
                "relevance_score": 0.5,
                "relevance_reasoning": "Czesciowa odpowiedz.",
                "latency_ms": 140.0,
            },
        ],
    }

    run_id = ingest_evaluation_run(mock_report, db_path=temp_db, golden_set_version="v1.0")

    assert run_id.startswith("run-")

    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()

        # Check runs table
        cursor.execute("SELECT commit_sha, mean_faithfulness, mean_relevance, p95_latency_ms FROM runs WHERE run_id = ?", (run_id,))
        run_row = cursor.fetchone()
        assert run_row is not None
        assert run_row[0] == "testsha123"
        assert run_row[1] == 0.95
        assert run_row[2] == 0.90
        assert run_row[3] == 150.5

        # Check test_results table
        cursor.execute("SELECT test_id, faithfulness_score, faithfulness_reasoning FROM test_results WHERE run_id = ?", (run_id,))
        results = cursor.fetchall()
        assert len(results) == 2
        test_ids = {r[0] for r in results}
        assert "eval-001" in test_ids
        assert "eval-002" in test_ids


def test_ingest_evaluation_run_from_file(tmp_path: Path, temp_db: Path):
    json_path = tmp_path / "report.json"
    json_path.write_text(
        """
        {
          "commit_sha": "abc456",
          "branch": "feature/rag-fix",
          "mean_faithfulness": 1.0,
          "mean_relevance": 1.0,
          "p95_latency_ms": 50.0,
          "total_cost_usd": 0.0005,
          "cases": []
        }
        """,
        encoding="utf-8",
    )

    run_id = ingest_evaluation_run(json_path, db_path=temp_db)
    assert run_id.startswith("run-")

    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT branch, mean_faithfulness FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row[0] == "feature/rag-fix"
        assert row[1] == 1.0
