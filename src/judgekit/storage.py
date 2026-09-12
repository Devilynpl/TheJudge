"""SQLite database storage and schema manager for evaluation run history."""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DEFAULT_DB_PATH = Path("data/eval_history.db")

CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    commit_sha TEXT,
    branch TEXT,
    mean_faithfulness REAL,
    mean_relevance REAL,
    p95_latency_ms REAL,
    total_cost_usd REAL,
    golden_set_version TEXT
);
"""

CREATE_TEST_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    test_id TEXT,
    query TEXT,
    generated_answer TEXT,
    faithfulness_score REAL,
    faithfulness_reasoning TEXT,
    relevance_score REAL,
    relevance_reasoning TEXT,
    latency_ms REAL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
"""


def init_db(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> Path:
    """Initialize the SQLite evaluation history database and tables.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Resolved Path to the initialized database.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_RUNS_TABLE)
        cursor.execute(CREATE_TEST_RESULTS_TABLE)
        # Helpful indices for fast querying in Streamlit
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_results_run_id ON test_results(run_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);")
        conn.commit()

    return path


def get_db_connection(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return an active connection to the SQLite database, initializing it if needed."""
    path = Path(db_path)
    if not path.exists():
        init_db(path)
    return sqlite3.connect(path)
