"""Tests for selector eval framework."""

from __future__ import annotations

from sre_agent.evals.selector_eval import format_selector_eval, run_selector_eval


class TestSelectorEval:
    def test_runs_without_error(self):
        result = run_selector_eval()
        assert result.total_scenarios >= 20
        assert result.passed > 0

    def test_recall_above_threshold(self):
        result = run_selector_eval()
        assert result.recall_at_5 >= 0.80, f"Recall@5 too low: {result.recall_at_5}"

    def test_latency_under_limit(self):
        import os

        result = run_selector_eval()
        limit = 500 if os.environ.get("CI") else 100
        assert result.latency_p99_ms < limit, f"Latency p99 too high: {result.latency_p99_ms}ms (limit {limit}ms)"

    def test_cold_start_coverage(self):
        result = run_selector_eval()
        assert result.cold_start_coverage >= 0.90

    def test_format_output(self):
        result = run_selector_eval()
        text = format_selector_eval(result)
        assert "Selector Eval" in text
        assert "Recall" in text
