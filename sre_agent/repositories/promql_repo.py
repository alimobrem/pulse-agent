"""PromQL repository -- learned PromQL query database operations.

Covers: promql_recipes.py (record_query_result, get_query_reliability,
get_reliable_queries).
"""

from __future__ import annotations

import logging

from .base import BaseRepository

logger = logging.getLogger("pulse_agent.promql")


class PromQLRepository(BaseRepository):
    """Database operations for PromQL query tracking."""

    def record_success(
        self,
        qhash: str,
        normalized: str,
        category: str,
        series_count: float,
    ) -> None:
        """Record a successful PromQL query."""
        self.db.execute(
            "INSERT INTO promql_queries (query_hash, query_template, category, success_count, last_success, avg_series_count) "
            "VALUES (%s, %s, %s, 1, NOW(), %s) "
            "ON CONFLICT (query_hash) DO UPDATE SET "
            "category = COALESCE(NULLIF(promql_queries.category, ''), %s), "
            "success_count = promql_queries.success_count + 1, "
            "last_success = NOW(), "
            "avg_series_count = (promql_queries.avg_series_count + %s) / 2",
            (qhash, normalized, category, series_count, category, series_count),
        )
        self.db.commit()

    def record_failure(
        self,
        qhash: str,
        normalized: str,
        category: str,
    ) -> None:
        """Record a failed PromQL query."""
        self.db.execute(
            "INSERT INTO promql_queries (query_hash, query_template, category, failure_count, last_failure) "
            "VALUES (%s, %s, %s, 1, NOW()) "
            "ON CONFLICT (query_hash) DO UPDATE SET "
            "category = COALESCE(NULLIF(promql_queries.category, ''), %s), "
            "failure_count = promql_queries.failure_count + 1, "
            "last_failure = NOW()",
            (qhash, normalized, category, category),
        )
        self.db.commit()

    def fetch_reliability(self, qhash: str) -> dict | None:
        """Fetch success/failure counts for a query hash."""
        return self.db.fetchone(
            "SELECT success_count, failure_count, avg_series_count FROM promql_queries WHERE query_hash = %s",
            (qhash,),
        )

    def fetch_reliable_queries(self, category: str, min_success: int) -> list[dict]:
        """Return queries with high success rates for a category."""
        return self.db.fetchall(
            "SELECT query_template, success_count, failure_count, avg_series_count "
            "FROM promql_queries WHERE category = %s AND success_count >= %s "
            "ORDER BY success_count DESC LIMIT 20",
            (category, min_success),
        )


# -- Singleton ---------------------------------------------------------------

_promql_repo: PromQLRepository | None = None


def get_promql_repo() -> PromQLRepository:
    """Return the module-level PromQLRepository singleton."""
    global _promql_repo
    if _promql_repo is None:
        _promql_repo = PromQLRepository()
    return _promql_repo
