"""Tests for tool usage REST endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("PULSE_AGENT_WS_TOKEN", "test-token-123")


class TestAgentsEndpoint:
    def test_returns_agents(self):
        from sre_agent.api import app

        client = TestClient(app)
        resp = client.get("/agents", headers={"Authorization": "Bearer test-token-123"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = {a["name"] for a in data}
        assert "sre" in names
        assert "security" in names

    def test_unauthorized(self):
        from sre_agent.api import app

        client = TestClient(app)
        resp = client.get("/agents")
        assert resp.status_code == 401


class TestToolsEndpointEnhanced:
    def test_includes_category(self):
        from sre_agent.api import app

        client = TestClient(app)
        resp = client.get("/tools", headers={"Authorization": "Bearer test-token-123"})
        assert resp.status_code == 200
        data = resp.json()
        sre_tools = data["sre"]
        assert len(sre_tools) > 0
        has_category = [t for t in sre_tools if t.get("category") is not None]
        assert len(has_category) > 0


class TestToolsUsageEndpoint:
    @patch("sre_agent.tool_usage.query_usage")
    def test_basic_query(self, mock_query):
        mock_query.return_value = {"entries": [], "total": 0, "page": 1, "per_page": 50}
        from sre_agent.api import app

        client = TestClient(app)
        resp = client.get("/tools/usage", headers={"Authorization": "Bearer test-token-123"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        mock_query.assert_called_once()

    @patch("sre_agent.tool_usage.query_usage")
    def test_passes_filters(self, mock_query):
        mock_query.return_value = {"entries": [], "total": 0, "page": 1, "per_page": 50}
        from sre_agent.api import app

        client = TestClient(app)
        resp = client.get(
            "/tools/usage?tool_name=list_pods&agent_mode=sre&status=success&page=2&per_page=10",
            headers={"Authorization": "Bearer test-token-123"},
        )
        assert resp.status_code == 200
        mock_query.assert_called_once_with(
            tool_name="list_pods",
            agent_mode="sre",
            status="success",
            session_id=None,
            time_from=None,
            time_to=None,
            page=2,
            per_page=10,
        )


class TestToolsUsageStatsEndpoint:
    @patch("sre_agent.tool_usage.get_usage_stats")
    def test_basic_stats(self, mock_stats):
        mock_stats.return_value = {
            "total_calls": 100,
            "unique_tools_used": 10,
            "error_rate": 0.05,
            "avg_duration_ms": 200,
            "avg_result_bytes": 3000,
            "by_tool": [],
            "by_mode": [],
            "by_category": [],
            "by_status": {},
        }
        from sre_agent.api import app

        client = TestClient(app)
        resp = client.get("/tools/usage/stats", headers={"Authorization": "Bearer test-token-123"})
        assert resp.status_code == 200
        assert resp.json()["total_calls"] == 100
