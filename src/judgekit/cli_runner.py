"""CLI interface for running JudgeKit evaluation suite."""

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from judgekit.dataset import load_golden_set
from judgekit.judge import JudgeClient
from judgekit.runner import EvalRunner, RAGResult


class StandaloneDemoRAG:
    """Mock/Fallback RAG pipeline when running standalone without external database."""

    def __init__(self, golden_cases):
        self.cases_map = {tc.query.strip().lower(): tc for tc in golden_cases}

    async def aquery(self, query: str) -> RAGResult:
        await asyncio.sleep(0.02)  # Simulate network/retrieval latency
        matched = self.cases_map.get(query.strip().lower())
        if matched and matched.reference_answer:
            return RAGResult(
                answer=matched.reference_answer,
                contexts=matched.reference_contexts or [],
                input_tokens=180,
                output_tokens=35,
            )
        elif matched:
            return RAGResult(
                answer=f"Dokumentacja nie zawiera informacji na to pytanie. ({matched.expected_behavior})",
                contexts=[],
                input_tokens=120,
                output_tokens=20,
            )
        return RAGResult(
            answer="Brak pasujących informacji w bazie wiedzy.",
            contexts=[],
            input_tokens=100,
            output_tokens=15,
        )


def get_git_commit_sha() -> str:
    """Get current git commit sha or return default."""
    try:
        res = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return res.decode("utf-8").strip()
    except Exception:
        return "local"


def get_git_branch() -> str:
    """Get current git branch or return default."""
    try:
        res = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL)
        return res.decode("utf-8").strip()
    except Exception:
        return "main"


def main():
    parser = argparse.ArgumentParser(description="JudgeKit Evaluation Runner CLI.")
    parser.add_argument(
        "--golden-set",
        type=str,
        default="tests/evals/data/golden_set.jsonl",
        help="Path to Golden Set .jsonl file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/candidate.json",
        help="Output destination path for evaluation JSON report.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=10,
        help="Maximum concurrent asynchronous tasks (default: 10).",
    )
    args = parser.parse_args()

    golden_path = Path(args.golden_set)
    if not golden_path.exists():
        print(f"[ERROR] Golden set file not found: {golden_path.resolve()}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading golden set from: {golden_path.resolve()}")
    test_cases = load_golden_set(golden_path)
    print(f"Loaded {len(test_cases)} test cases.")

    rag = StandaloneDemoRAG(test_cases)
    judge = JudgeClient(llm_client=None)

    runner = EvalRunner(rag_client=rag, judge_client=judge, max_concurrency=args.max_concurrency)

    commit_sha = get_git_commit_sha()
    branch = get_git_branch()

    print(f"Executing evaluation suite for commit [{commit_sha}] on branch [{branch}]...")
    summary = asyncio.run(runner.run_suite(test_cases, commit_sha=commit_sha, branch=branch))

    out_path = runner.export_report(summary, args.output)
    print("=" * 60)
    print("JUDGEKIT: PODSUMOWANIE EWALUACJI RUNNERA")
    print("=" * 60)
    print(f"Commit SHA:            {summary.commit_sha}")
    print(f"Branch:                {summary.branch}")
    print(f"Przetestowane przypadki: {summary.total_cases}")
    print(f"Mean Faithfulness:     {summary.mean_faithfulness:.4f}")
    print(f"Mean Relevance:        {summary.mean_relevance:.4f}")
    print(f"P50 Latency:           {summary.p50_latency_ms:.2f} ms")
    print(f"P95 Latency:           {summary.p95_latency_ms:.2f} ms")
    print(f"Krytyczne porazki:     {summary.critical_failures}")
    print(f"Calkowity koszt USD:   ${summary.total_cost_usd:.6f}")
    print("=" * 60)
    print(f"[SUCCESS] Raport zapisano w: {out_path.resolve()}")


if __name__ == "__main__":
    main()
