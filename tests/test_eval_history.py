"""Tests for eval run history persistence."""

from __future__ import annotations

from sre_agent.evals.history import get_eval_history, get_eval_trend, record_eval_run


class TestRecordEvalRun:
    def test_fire_and_forget_no_exception(self):
        """Recording should never raise, even without a DB."""
        record_eval_run(
            suite_name="test",
            source="test",
            scenario_count=5,
            passed_count=4,
            gate_passed=True,
            average_overall=0.85,
            dimensions={"task_success": 0.9, "safety": 1.0},
            blocker_counts={},
        )

    def test_with_all_fields(self):
        record_eval_run(
            suite_name="release",
            source="cli",
            model="claude-sonnet-4-6",
            scenario_count=20,
            passed_count=18,
            gate_passed=True,
            average_overall=0.92,
            dimensions={"task_success": 0.95, "safety": 1.0, "tool_efficiency": 0.85},
            blocker_counts={"policy_violation": 1},
            scenarios=[{"scenario_id": "s1", "overall": 0.9, "passed_gate": True}],
            prompt_audit={"sre": {"total_chars": 10000, "estimated_tokens": 2500}},
            judge_avg=88.5,
        )


class TestGetEvalHistory:
    def test_returns_list(self):
        result = get_eval_history(suite_name="release", days=30)
        assert isinstance(result, list)

    def test_returns_empty_without_db(self):
        result = get_eval_history(suite_name="nonexistent", days=1)
        assert result == []


class TestGetEvalTrend:
    def test_returns_dict(self):
        result = get_eval_trend(suite_name="release", days=30)
        assert isinstance(result, dict)
        assert "suite" in result

    def test_no_runs_returns_zero(self):
        result = get_eval_trend(suite_name="nonexistent_suite_xyz", days=1)
        assert result["runs"] == 0
