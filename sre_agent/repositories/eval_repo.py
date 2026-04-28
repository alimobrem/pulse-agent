"""Eval repository -- eval run history database operations.

Covers: evals/history.py (record_eval_run, get_eval_history, get_eval_trend).
"""

from __future__ import annotations

import logging

from .base import BaseRepository

logger = logging.getLogger("pulse_agent.evals.history")


class EvalRepository(BaseRepository):
    """Database operations for eval run history."""

    def record_run(
        self,
        *,
        suite_name: str,
        source: str,
        model: str,
        scenario_count: int,
        passed_count: int,
        gate_passed: bool,
        average_overall: float,
        dimensions_json: str | None,
        blocker_counts_json: str | None,
        scenarios_json: str | None,
        prompt_audit_json: str | None,
        judge_avg: float | None,
    ) -> None:
        """Record an eval run."""
        self.db.execute(
            "INSERT INTO eval_runs "
            "(suite_name, source, model, scenario_count, passed_count, gate_passed, "
            "average_overall, dimensions, blocker_counts, scenarios, prompt_audit, judge_avg) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                suite_name,
                source,
                model,
                scenario_count,
                passed_count,
                gate_passed,
                average_overall,
                dimensions_json,
                blocker_counts_json,
                scenarios_json,
                prompt_audit_json,
                judge_avg,
            ),
        )
        self.db.commit()

    def fetch_history(self, where: str, params: tuple, limit: int) -> list[dict]:
        """Fetch eval run history rows."""
        return self.db.fetchall(
            f"SELECT id, timestamp, suite_name, source, model, scenario_count, "
            f"passed_count, gate_passed, average_overall, dimensions, "
            f"blocker_counts, judge_avg "
            f"FROM eval_runs {where} "
            f"ORDER BY timestamp DESC LIMIT %s",
            params + (limit,),
        )

    def fetch_trend(self, suite_name: str, days: int, limit: int = 50) -> list[dict]:
        """Fetch recent eval runs for trend analysis."""
        return self.db.fetchall(
            "SELECT timestamp, average_overall, gate_passed, judge_avg "
            "FROM eval_runs "
            "WHERE suite_name = %s AND timestamp > NOW() - INTERVAL '1 day' * %s "
            "ORDER BY timestamp DESC LIMIT %s",
            (suite_name, days, limit),
        )


# -- Singleton ---------------------------------------------------------------

_eval_repo: EvalRepository | None = None


def get_eval_repo() -> EvalRepository:
    """Return the module-level EvalRepository singleton."""
    global _eval_repo
    if _eval_repo is None:
        _eval_repo = EvalRepository()
    return _eval_repo
