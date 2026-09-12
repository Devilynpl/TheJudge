"""Unit tests for PR commenter and markdown generation."""

import json
from pathlib import Path
import pytest
import httpx

from judgekit.pr_commenter import (
    COMMENT_HEADER_TAG,
    format_delta,
    generate_pr_markdown_report,
    post_or_update_pr_comment,
)


def test_format_delta():
    assert format_delta(0.0) == "0.0000"
    assert format_delta(0.025, decimals=4) == "**+0.0250**"
    assert format_delta(-0.015, decimals=4) == "**-0.0150**"
    assert format_delta(290.0, unit=" ms", decimals=1) == "**+290.0 ms**"
    assert format_delta(0, decimals=0) == "0"


def test_generate_pr_markdown_report_passed():
    diff_report = {
        "baseline_commit": "abc1234",
        "candidate_commit": "def5678",
        "delta_faithfulness": 0.025,
        "delta_relevance": 0.0,
        "delta_p95_latency_ms": 10.5,
        "regressions": [],
        "improvements": [],
        "critical_regressions_count": 0,
        "total_compared_cases": 20,
    }
    baseline = {
        "mean_faithfulness": 0.85,
        "mean_relevance": 0.90,
        "p95_latency_ms": 320.0,
    }
    candidate = {
        "mean_faithfulness": 0.875,
        "mean_relevance": 0.90,
        "p95_latency_ms": 330.5,
    }

    md = generate_pr_markdown_report(diff_report, baseline, candidate)

    assert COMMENT_HEADER_TAG in md
    assert "EVAL_PASSED" in md
    assert "Faithfulness" in md
    assert "0.8500" in md
    assert "0.8750" in md
    assert "**+0.0250**" in md
    assert "Brak regresji jakościowych" in md


def test_generate_pr_markdown_report_blocked_with_regressions():
    diff_report = {
        "baseline_commit": "abc1234",
        "candidate_commit": "def5678",
        "delta_faithfulness": -0.05,
        "delta_relevance": -0.01,
        "delta_p95_latency_ms": 300.0,
        "regressions": [
            {
                "test_id": "eval-015",
                "metric": "faithfulness",
                "baseline_score": 1.0,
                "candidate_score": 0.0,
                "diff": -1.0,
                "reason": "Model pominal kluczowy warunek gwarancji.",
            }
        ],
        "improvements": [],
        "critical_regressions_count": 1,
        "total_compared_cases": 20,
    }

    md = generate_pr_markdown_report(diff_report)

    assert "EVAL_BLOCKED" in md
    assert "eval-015" in md
    assert "Model pominal kluczowy warunek gwarancji." in md
    assert "<details>" in md
    assert "Zidentyfikowane regresje jakościowe" in md
    assert "Powody odrzucenia przez Quality Gate:" in md


def test_post_or_update_pr_comment_create_new(monkeypatch):
    """Test creating a new comment when none exists."""
    created = {}

    def mock_handler(request: httpx.Request):
        if request.method == "GET" and "/comments" in str(request.url):
            return httpx.Response(200, json=[{"id": 1, "body": "Other bot comment"}])
        if request.method == "POST" and "/comments" in str(request.url):
            payload = json.loads(request.content.decode("utf-8"))
            created["body"] = payload["body"]
            return httpx.Response(201, json={"id": 42, "html_url": "https://github.com/test/pr/1#issuecomment-42"})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)

    client_orig = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *args, **kwargs: client_orig(transport=transport, base_url=kwargs.get("base_url", "https://api.github.com")),
    )

    res = post_or_update_pr_comment(
        repo="Devilynpl/TheJudge",
        pr_number=1,
        body=f"{COMMENT_HEADER_TAG}\nTest Comment",
        github_token="ghp_dummy",
    )

    assert res["id"] == 42
    assert "Test Comment" in created["body"]


def test_post_or_update_pr_comment_update_existing(monkeypatch):
    """Test updating existing comment when header tag matches."""
    updated = {}

    def mock_handler(request: httpx.Request):
        if request.method == "GET" and "/comments" in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "body": "Some normal comment"},
                    {"id": 99, "body": f"{COMMENT_HEADER_TAG}\nOld Report"},
                ],
            )
        if request.method == "PATCH" and "/comments/99" in str(request.url):
            payload = json.loads(request.content.decode("utf-8"))
            updated["body"] = payload["body"]
            return httpx.Response(200, json={"id": 99, "html_url": "https://github.com/test/pr/1#issuecomment-99"})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)

    client_orig = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *args, **kwargs: client_orig(transport=transport, base_url=kwargs.get("base_url", "https://api.github.com")),
    )

    res = post_or_update_pr_comment(
        repo="Devilynpl/TheJudge",
        pr_number=1,
        body=f"{COMMENT_HEADER_TAG}\nNew Updated Report",
        github_token="ghp_dummy",
    )

    assert res["id"] == 99
    assert "New Updated Report" in updated["body"]
