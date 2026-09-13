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
        "--target",
        type=str,
        default=None,
        help="Target adapter spec 'module.path:ClassName' or 'path/to/file.py:ClassName'. Defaults to internal demo RAG.",
    )
    parser.add_argument(
        "--golden-set",
        "--suite",
        dest="golden_set",
        type=str,
        default="tests/evals/data/golden_set.jsonl",
        help="Path to Golden Set / Evaluation Suite .jsonl file.",
    )
    parser.add_argument(
        "--gate-config",
        type=str,
        default=None,
        help="Optional path to Quality Gate JSON config to enforce gate check immediately.",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        choices=["judge", "ragas", "both"],
        default="judge",
        help="Metrics engine: 'judge' (LLM-as-a-Judge), 'ragas' (4 RAGAS metrics), or 'both' (concurrent dual-track).",
    )
    parser.add_argument(
        "--trace-phoenix",
        action="store_true",
        default=False,
        help="Enable Arize Phoenix retrieval & evaluation span tracing.",
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

    print(f"Loading golden set / suite from: {golden_path.resolve()}")
    test_cases = load_golden_set(golden_path)
    print(f"Loaded {len(test_cases)} test cases.")

    # Initialize target system
    cases_map = {tc.query.strip().lower(): tc for tc in test_cases}
    if args.target:
        from judgekit.target_runner import load_target_adapter, TargetRunnerBridge
        print(f"Loading dynamic target adapter: {args.target}")
        adapter = load_target_adapter(args.target)
        rag = TargetRunnerBridge(adapter, cases_map=cases_map)
    else:
        rag = StandaloneDemoRAG(test_cases)

    from judgekit.metrics.ragas_metrics import RagasEvaluator
    from judgekit.tracing.phoenix import PhoenixTracer

    judge = JudgeClient(llm_client=None)
    ragas_eval = RagasEvaluator() if args.metrics in ("ragas", "both") else None
    tracer = PhoenixTracer(enabled=args.trace_phoenix)

    runner = EvalRunner(
        rag_client=rag,
        judge_client=judge,
        ragas_evaluator=ragas_eval,
        metrics_mode=args.metrics,
        tracer=tracer,
        max_concurrency=args.max_concurrency,
    )

    commit_sha = get_git_commit_sha()
    branch = get_git_branch()

    print(f"Executing evaluation suite for commit [{commit_sha}] on branch [{branch}] (metrics: {args.metrics})...")
    summary = asyncio.run(runner.run_suite(test_cases, commit_sha=commit_sha, branch=branch))

    out_path = runner.export_report(summary, args.output)
    print("=" * 60)
    print("JUDGEKIT: PODSUMOWANIE EWALUACJI RUNNERA")
    print("=" * 60)
    print(f"Commit SHA:              {summary.commit_sha}")
    print(f"Branch:                  {summary.branch}")
    print(f"Tryb metryk:             {summary.metrics_mode.upper()}")
    print(f"Przetestowane przypadki: {summary.total_cases}")
    print(f"Mean Faithfulness:       {summary.mean_faithfulness:.4f}")
    print(f"Mean Relevance:          {summary.mean_relevance:.4f}")
    if summary.ragas_mean_faithfulness is not None:
        print(f"RAGAS Faithfulness:      {summary.ragas_mean_faithfulness:.4f}")
    if summary.ragas_mean_answer_relevancy is not None:
        print(f"RAGAS Answer Relevancy:  {summary.ragas_mean_answer_relevancy:.4f}")
    if summary.ragas_mean_context_precision is not None:
        print(f"RAGAS Context Precision: {summary.ragas_mean_context_precision:.4f}")
    if summary.ragas_mean_context_recall is not None:
        print(f"RAGAS Context Recall:    {summary.ragas_mean_context_recall:.4f}")
    if summary.mean_citation_precision is not None:
        print(f"Mean Citation Precision: {summary.mean_citation_precision:.4f}")
    if summary.refusal_accuracy is not None:
        print(f"Refusal Accuracy:        {summary.refusal_accuracy*100:.1f}%")
    if summary.mean_rubric_score is not None:
        print(f"Mean Rubric Score:       {summary.mean_rubric_score:.4f}")
    if summary.stealth_accuracy is not None:
        print(f"Stealth Zero-Halluc:     {summary.stealth_accuracy*100:.1f}%")
    if summary.budget_compliance_rate is not None:
        print(f"Budget Compliance Rate:  {summary.budget_compliance_rate*100:.1f}%")
    if summary.avg_steps is not None:
        print(f"Avg Steps Taken:         {summary.avg_steps:.2f}")
    print(f"P50 Latency:             {summary.p50_latency_ms:.2f} ms")
    print(f"P95 Latency:             {summary.p95_latency_ms:.2f} ms")
    print(f"Krytyczne porazki:       {summary.critical_failures}")
    print(f"Calkowity koszt USD:     ${summary.total_cost_usd:.6f}")
    print("=" * 60)
    print(f"[SUCCESS] Raport zapisano w: {out_path.resolve()}")

    if args.trace_phoenix and tracer.spans:
        trace_path = Path("artifacts/phoenix_traces.jsonl")
        tracer.export_traces_jsonl(trace_path)
        print(f"[TRACING] Wyeksportowano {len(tracer.spans)} spanów Phoenix do: {trace_path.resolve()}")

    # If --gate-config provided, evaluate gate rules directly
    if args.gate_config:
        from judgekit.gate import evaluate_absolute_gate_rules
        gate_cfg_path = Path(args.gate_config)
        print("\n" + "=" * 60)
        print(f"JUDGEKIT: WERYFIKACJA BRAMKI JAKOSCI ({gate_cfg_path.name})")
        print("=" * 60)
        gate_res = evaluate_absolute_gate_rules(summary, gate_config=gate_cfg_path)
        if not gate_res.passed:
            print("[FAIL] Bramka CI odrzuciła wyniki ewaluacji:")
            for reason in gate_res.failure_reasons:
                print(f"  [X] {reason}")
            sys.exit(1)
        else:
            print("[PASS] Wszystkie warunki bramki jakości zostały spełnione!")


if __name__ == "__main__":
    main()

