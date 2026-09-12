"""Ingestion service to parse evaluation runs and insert records into SQLite."""

import argparse
import datetime
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

from judgekit.storage import DEFAULT_DB_PATH, init_db


def ingest_evaluation_run(
    report_data_or_path: Union[Dict[str, Any], str, Path],
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
    golden_set_version: str = "v1.0",
    run_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> str:
    """Ingest a JudgeReport (JSON file or Dict) into SQLite runs & test_results.

    Args:
        report_data_or_path: Path to JSON evaluation report or parsed dict.
        db_path: Path to target SQLite database file.
        golden_set_version: Golden set version tag.
        run_id: Unique run ID (auto-generated UUID4 if None).
        timestamp: ISO timestamp or None for current UTC timestamp.

    Returns:
        The run_id of the newly inserted run record.
    """
    if isinstance(report_data_or_path, (str, Path)):
        p = Path(report_data_or_path)
        if not p.exists():
            raise FileNotFoundError(f"Evaluation report file not found: {p.resolve()}")
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = report_data_or_path

    # Ensure DB tables are ready
    resolved_db = init_db(db_path)

    assigned_run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    assigned_timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    commit_sha = str(data.get("commit_sha", "unknown"))
    branch = str(data.get("branch", "main"))
    mean_faith = float(data.get("mean_faithfulness", 0.0))
    mean_rel = float(data.get("mean_relevance", 0.0))
    p95_lat = float(data.get("p95_latency_ms", 0.0))
    total_cost = float(data.get("total_cost_usd", 0.0))

    with sqlite3.connect(resolved_db) as conn:
        cursor = conn.cursor()

        # Insert run aggregate
        cursor.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, timestamp, commit_sha, branch,
                mean_faithfulness, mean_relevance, p95_latency_ms,
                total_cost_usd, golden_set_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assigned_run_id,
                assigned_timestamp,
                commit_sha,
                branch,
                mean_faith,
                mean_rel,
                p95_lat,
                total_cost,
                golden_set_version,
            ),
        )

        # Insert individual test results
        cases = data.get("cases", [])
        for c in cases:
            cursor.execute(
                """
                INSERT INTO test_results (
                    run_id, test_id, query, generated_answer,
                    faithfulness_score, faithfulness_reasoning,
                    relevance_score, relevance_reasoning, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assigned_run_id,
                    c.get("test_id", "unknown"),
                    c.get("query", ""),
                    c.get("generated_answer", ""),
                    c.get("faithfulness_score", 0.0),
                    c.get("faithfulness_reasoning", ""),
                    c.get("relevance_score", 0.0),
                    c.get("relevance_reasoning", ""),
                    c.get("latency_ms", 0.0),
                ),
            )

        conn.commit()

    return assigned_run_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest JudgeKit evaluation JSON into historical SQLite database."
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to evaluation report JSON (e.g. artifacts/baseline.json).",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--golden-set-version",
        default="v1.0",
        help="Golden set version identifier (default: v1.0).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Custom run ID string (optional).",
    )

    args = parser.parse_args()

    run_id = ingest_evaluation_run(
        report_data_or_path=args.report,
        db_path=args.db,
        golden_set_version=args.golden_set_version,
        run_id=args.run_id,
    )
    print(f"Successfully ingested evaluation run: {run_id} into {args.db}")


if __name__ == "__main__":
    main()
