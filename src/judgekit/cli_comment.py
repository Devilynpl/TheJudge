"""CLI tool for generating and posting PR evaluation comments."""

import argparse
import os
import sys
from pathlib import Path

# Ensure UTF-8 stdout on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from judgekit.pr_commenter import generate_pr_markdown_report, post_or_update_pr_comment



def main() -> None:
    parser = argparse.ArgumentParser(
        description="JudgeKit PR Markdown Reporting Bot."
    )
    parser.add_argument(
        "--diff-report",
        required=True,
        help="Path to diff_report.json produced by comparator.",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Optional path to baseline.json.",
    )
    parser.add_argument(
        "--candidate",
        default=None,
        help="Optional path to candidate.json.",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Optional file path to export rendered Markdown.",
    )
    parser.add_argument(
        "--post-to-pr",
        action="store_true",
        help="Post or update comment on GitHub PR using GITHUB_TOKEN and env vars.",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="Repository in 'owner/repo' format (defaults to $GITHUB_REPOSITORY).",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        default=int(os.environ.get("PR_NUMBER", 0)) if os.environ.get("PR_NUMBER") else None,
        help="Pull Request number (defaults to $PR_NUMBER).",
    )
    parser.add_argument(
        "--github-token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub API token (defaults to $GITHUB_TOKEN).",
    )

    args = parser.parse_args()

    # Generate Markdown
    md_content = generate_pr_markdown_report(
        diff_report_data_or_path=args.diff_report,
        baseline_data_or_path=args.baseline,
        candidate_data_or_path=args.candidate,
    )

    if args.output_md:
        out_path = Path(args.output_md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"PR Comment Markdown written to {out_path.resolve()}")
    else:
        print(md_content)

    if args.post_to_pr:
        if not args.repo:
            print("Error: Missing --repo or GITHUB_REPOSITORY.", file=sys.stderr)
            sys.exit(1)
        if not args.pr_number:
            print("Error: Missing --pr-number or PR_NUMBER.", file=sys.stderr)
            sys.exit(1)
        if not args.github_token:
            print("Error: Missing --github-token or GITHUB_TOKEN.", file=sys.stderr)
            sys.exit(1)

        print(f"Posting/updating comment on PR #{args.pr_number} in {args.repo}...")
        res = post_or_update_pr_comment(
            repo=args.repo,
            pr_number=args.pr_number,
            body=md_content,
            github_token=args.github_token,
        )
        print(f"Comment successfully synchronized (ID: {res.get('id')}). URL: {res.get('html_url')}")


if __name__ == "__main__":
    main()
