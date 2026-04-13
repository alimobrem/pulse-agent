"""Tests for the intelligence loop module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import sre_agent.intelligence as intel_module
from sre_agent.intelligence import get_intelligence_context


def _mock_db(fetchall_returns=None, fetchone_returns=None):
    """Create a mock database with configurable returns."""
    db = MagicMock()
    db.fetchall.return_value = fetchall_returns or []
    db.fetchone.return_value = fetchone_returns
    return patch("sre_agent.db.get_database", return_value=db)


class TestQueryReliability:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_preferred_queries_shown(self):
        rows = [
            {"query_template": "sum(rate(cpu[5m]))", "success_count": 47, "failure_count": 0},
            {"query_template": "avg(memory_bytes)", "success_count": 23, "failure_count": 1},
        ]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert "USE THIS" in result
        assert "cpu" in result

    def test_avoid_queries_shown(self):
        rows = [
            {"query_template": "predict_linear(disk[7d])", "success_count": 1, "failure_count": 8},
            {"query_template": "etcd_pending", "success_count": 0, "failure_count": 5},
        ]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert "AVOID" in result

    def test_mid_range_queries_excluded(self):
        # success_rate 0.5 — neither preferred (>0.8) nor avoid (<0.3)
        rows = [
            {"query_template": "rare_query", "success_count": 5, "failure_count": 5},
        ]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert "rare_query" not in result

    def test_query_truncated(self):
        long_query = "a" * 200
        rows = [
            {"query_template": long_query, "success_count": 10, "failure_count": 0},
        ]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert long_query not in result
        assert "..." in result

    def test_preferred_limit_10(self):
        rows = [{"query_template": f"query_{i}", "success_count": 100, "failure_count": 0} for i in range(15)]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert result.count("USE THIS") == 10

    def test_avoid_limit_5(self):
        rows = [{"query_template": f"bad_query_{i}", "success_count": 0, "failure_count": 10} for i in range(8)]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert result.count("AVOID") == 5


class TestDashboardPatterns:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_most_used_tools_listed(self):
        call_count = [0]

        def mock_fetchall(sql, params=None):
            call_count[0] += 1
            if "promql_queries" in sql:
                return []
            if "GROUP BY tool_name" in sql and "view_designer" in sql:
                return [
                    {"tool_name": "cluster_metrics", "call_count": 15},
                    {"tool_name": "get_prometheus_query", "call_count": 42},
                ]
            if "HAVING" in sql:
                return []
            return []

        db = MagicMock()
        db.fetchall.side_effect = mock_fetchall
        db.fetchone.return_value = {"avg_tools": 5}

        with patch("sre_agent.db.get_database", return_value=db):
            result = get_intelligence_context()
        assert "cluster_metrics" in result
        assert "get_prometheus_query" in result

    def test_avg_tools_shown(self):
        def mock_fetchall(sql, params=None):
            if "promql_queries" in sql:
                return []
            if "GROUP BY tool_name" in sql and "view_designer" in sql:
                return [{"tool_name": "list_pods", "call_count": 8}]
            if "HAVING" in sql:
                return []
            return []

        db = MagicMock()
        db.fetchall.side_effect = mock_fetchall
        db.fetchone.return_value = {"avg_tools": 7}

        with patch("sre_agent.db.get_database", return_value=db):
            result = get_intelligence_context()
        assert "7" in result
        assert "Average tools" in result

    def test_empty_dashboard_patterns(self):
        def mock_fetchall(sql, params=None):
            return []

        db = MagicMock()
        db.fetchall.side_effect = mock_fetchall
        db.fetchone.return_value = None

        with patch("sre_agent.db.get_database", return_value=db):
            result = get_intelligence_context()
        assert "Dashboard Patterns" not in result


class TestErrorHotspots:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_high_error_rate_flagged(self):
        def mock_fetchall(sql, params=None):
            if "promql_queries" in sql:
                return []
            if "GROUP BY tool_name" in sql and "view_designer" in sql:
                return []
            # CTE query for error hotspots (batch query with top_errors)
            if "hotspots" in sql and "top_errors" in sql:
                return [
                    {
                        "tool_name": "get_prometheus_query",
                        "error_count": 32,
                        "total_count": 267,
                        "common_error": "Query returned no results",
                    }
                ]
            if "HAVING" in sql:
                return [{"tool_name": "get_prometheus_query", "error_count": 32, "total_count": 267}]
            return []

        db = MagicMock()
        db.fetchall.side_effect = mock_fetchall
        db.fetchone.return_value = None

        with patch("sre_agent.db.get_database", return_value=db):
            result = get_intelligence_context()
        assert "get_prometheus_query" in result
        assert "error rate" in result
        assert "Query returned no results" in result

    def test_error_rate_percentage(self):
        def mock_fetchall(sql, params=None):
            if "promql_queries" in sql:
                return []
            if "view_designer" in sql:
                return []
            # CTE query for error hotspots
            if "hotspots" in sql and "top_errors" in sql:
                return [{"tool_name": "list_pods", "error_count": 10, "total_count": 100, "common_error": ""}]
            if "HAVING" in sql:
                return [{"tool_name": "list_pods", "error_count": 10, "total_count": 100}]
            return []

        db = MagicMock()
        db.fetchall.side_effect = mock_fetchall
        db.fetchone.return_value = None

        with patch("sre_agent.db.get_database", return_value=db):
            result = get_intelligence_context()
        assert "10.0%" in result


class TestCaching:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_cache_used_on_second_call(self):
        with _mock_db() as mock_get_db:
            get_intelligence_context()
            first_count = mock_get_db.call_count
            get_intelligence_context()
        # Second call should not increase DB call count (served from cache)
        assert mock_get_db.call_count == first_count

    def test_cache_expired_queries_again(self):
        intel_module._intelligence_cache["sre"] = ("old data", 0)  # ancient timestamp
        with _mock_db() as mock_get_db:
            result = get_intelligence_context()
        # Should have queried the DB (cache was expired)
        assert mock_get_db.call_count >= 1
        assert result != "old data"

    def test_cache_keyed_by_mode(self):
        with _mock_db() as mock_get_db:
            get_intelligence_context(mode="sre")
            sre_count = mock_get_db.call_count
            get_intelligence_context(mode="security")
        # Security mode should trigger additional DB calls
        assert mock_get_db.call_count > sre_count

    def test_cached_value_returned(self):
        intel_module._intelligence_cache["sre"] = ("cached result", float("inf"))
        result = get_intelligence_context(mode="sre")
        assert result == "cached result"


class TestIntegration:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_empty_db_returns_empty(self):
        with _mock_db():
            result = get_intelligence_context()
        assert result == ""

    def test_db_error_returns_empty(self):
        with patch("sre_agent.db.get_database", side_effect=Exception("DB down")):
            result = get_intelligence_context()
        assert result == ""

    def test_returns_string(self):
        rows = [{"query_template": "sum(cpu)", "success_count": 10, "failure_count": 0}]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert isinstance(result, str)

    def test_header_present(self):
        rows = [{"query_template": "sum(cpu)", "success_count": 10, "failure_count": 0}]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context()
        assert "## Agent Intelligence (last 7 days)" in result

    def test_custom_max_age(self):
        rows = [{"query_template": "sum(cpu)", "success_count": 10, "failure_count": 0}]
        with _mock_db(fetchall_returns=rows):
            result = get_intelligence_context(max_age_days=30)
        assert "last 30 days" in result


class TestHarnessEffectiveness:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_harness_effectiveness_returns_string(self):
        def mock_fetchall(sql, params=None):
            if "promql_queries" in sql:
                return []
            if "view_designer" in sql:
                return []
            if "HAVING" in sql:
                return []
            if "unnest" in sql:
                return [
                    {"tool_name": "analyze_hpa_thrashing", "offered_count": 52, "called_count": 1},
                    {"tool_name": "forecast_quota_exhaustion", "offered_count": 48, "called_count": 0},
                ]
            return []

        def mock_fetchone(sql, params=None):
            if "array_length(tools_called" in sql:
                return {"accuracy": 0.34, "avg_called": 5, "avg_offered": 15}
            if "input_tokens" in sql and "FILTER" not in sql:
                return None
            return None

        db = MagicMock()
        db.fetchall.side_effect = mock_fetchall
        db.fetchone.side_effect = mock_fetchone

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_harness_effectiveness(7)

        assert isinstance(result, str)
        assert "Harness Effectiveness" in result
        assert "34%" in result
        assert "analyze_hpa_thrashing" in result

    def test_harness_effectiveness_empty_data(self):
        db = MagicMock()
        db.fetchone.return_value = {"accuracy": None, "avg_called": 0, "avg_offered": 0}
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_harness_effectiveness(7)
        assert result == ""


class TestRoutingAccuracy:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_routing_accuracy_returns_string(self):
        db = MagicMock()
        db.fetchone.return_value = {"switches": 15, "total": 100}
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_routing_accuracy(7)

        assert isinstance(result, str)
        assert "Routing Accuracy" in result
        assert "85%" in result
        assert "15" in result

    def test_routing_accuracy_empty_data(self):
        db = MagicMock()
        db.fetchone.return_value = {"switches": 0, "total": 0}
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_routing_accuracy(7)
        assert result == ""


class TestFeedbackAnalysis:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_feedback_analysis_returns_string(self):
        db = MagicMock()
        db.fetchall.return_value = [
            {"tool_name": "get_prometheus_query", "negative": 3, "total": 10},
        ]
        db.fetchone.return_value = None

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_feedback_analysis(7)

        assert isinstance(result, str)
        assert "Feedback Analysis" in result
        assert "get_prometheus_query" in result
        assert "3 negative" in result

    def test_feedback_analysis_empty_data(self):
        db = MagicMock()
        db.fetchall.return_value = []
        db.fetchone.return_value = None

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_feedback_analysis(7)
        assert result == ""


class TestTokenTrending:
    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_token_trending_returns_string(self):
        db = MagicMock()
        db.fetchone.return_value = {
            "current_input": 3200,
            "prev_input": 3636,
            "current_output": 1100,
            "prev_output": 1000,
            "current_cache": 500,
            "prev_cache": 400,
        }
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_token_trending(7)

        assert isinstance(result, str)
        assert "Token Trending" in result
        assert "3,200" in result
        assert "1,100" in result

    def test_token_trending_no_prev(self):
        db = MagicMock()
        db.fetchone.return_value = {
            "current_input": 2500,
            "prev_input": None,
            "current_output": 800,
            "prev_output": None,
            "current_cache": None,
            "prev_cache": None,
        }
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_token_trending(7)

        assert "2,500" in result
        assert "from last week" not in result

    def test_token_trending_empty_data(self):
        db = MagicMock()
        db.fetchone.return_value = {
            "current_input": None,
            "prev_input": None,
            "current_output": None,
            "prev_output": None,
            "current_cache": None,
            "prev_cache": None,
        }
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            result = intel_module._compute_token_trending(7)
        assert result == ""


class TestNewMetricsEmptyData:
    """Verify all new compute functions return empty string on no data."""

    def setup_method(self):
        intel_module._intelligence_cache.clear()

    def test_empty_data_returns_empty(self):
        db = MagicMock()
        db.fetchone.return_value = None
        db.fetchall.return_value = []

        with patch("sre_agent.db.get_database", return_value=db):
            assert intel_module._compute_harness_effectiveness(7) == ""
            assert intel_module._compute_routing_accuracy(7) == ""
            assert intel_module._compute_feedback_analysis(7) == ""
            assert intel_module._compute_token_trending(7) == ""
