"""HTTP-level tests for the 21 REST endpoints in sre_agent/api.py.

Tests authentication, response shapes, error handling, and status codes.
All K8s clients and database operations are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def pulse_token():
    return "test-token-secure-xyz"


@pytest.fixture
def api_headers(pulse_token):
    return {"Authorization": f"Bearer {pulse_token}"}


@pytest.fixture
def api_client(pulse_token, monkeypatch, tmp_path):
    monkeypatch.setenv("PULSE_AGENT_WS_TOKEN", pulse_token)
    monkeypatch.setenv("PULSE_AGENT_MEMORY", "0")
    monkeypatch.setenv("PULSE_AGENT_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    with (
        patch("sre_agent.k8s_client._initialized", True),
        patch("sre_agent.k8s_client._load_k8s"),
        patch("sre_agent.k8s_tools.get_core_client") as core,
        patch("sre_agent.k8s_tools.get_apps_client"),
        patch("sre_agent.k8s_tools.get_custom_client"),
        patch("sre_agent.k8s_tools.get_version_client"),
    ):
        core.return_value = MagicMock()
        from sre_agent.api import app

        client = TestClient(app, raise_server_exceptions=False)
        yield client


# ── Unauthenticated Endpoints ──────────────────────────────────────────────


class TestPublicEndpoints:
    def test_healthz(self, api_client):
        r = api_client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_version(self, api_client):
        r = api_client.get("/version")
        assert r.status_code == 200
        data = r.json()
        assert "protocol" in data
        assert "agent" in data
        assert "tools" in data
        assert "features" in data


# ── Authentication ──────────────────────────────────────────────────────────


class TestAuthentication:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "/health",
            "/tools",
            "/fix-history",
            "/briefing",
            "/memory/stats",
            "/memory/export",
            "/context",
            "/monitor/capabilities",
        ],
    )
    def test_missing_token_returns_401(self, api_client, endpoint):
        r = api_client.get(endpoint)
        assert r.status_code == 401

    @pytest.mark.parametrize("endpoint", ["/health", "/tools"])
    def test_invalid_token_returns_401(self, api_client, endpoint):
        r = api_client.get(endpoint, headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    @pytest.mark.parametrize("endpoint", ["/health", "/tools"])
    def test_bearer_header_auth(self, api_client, api_headers, endpoint):
        r = api_client.get(endpoint, headers=api_headers)
        assert r.status_code == 200

    @pytest.mark.parametrize("endpoint", ["/health", "/tools"])
    def test_query_param_auth(self, api_client, pulse_token, endpoint):
        r = api_client.get(endpoint, params={"token": pulse_token})
        assert r.status_code == 200

    def test_server_not_configured(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PULSE_AGENT_WS_TOKEN", "")
        monkeypatch.setenv("PULSE_AGENT_MEMORY", "0")
        monkeypatch.setenv("PULSE_AGENT_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
        with (
            patch("sre_agent.k8s_client._initialized", True),
            patch("sre_agent.k8s_client._load_k8s"),
            patch("sre_agent.k8s_tools.get_core_client", return_value=MagicMock()),
            patch("sre_agent.k8s_tools.get_apps_client"),
            patch("sre_agent.k8s_tools.get_custom_client"),
            patch("sre_agent.k8s_tools.get_version_client"),
        ):
            from sre_agent.api import app

            client = TestClient(app, raise_server_exceptions=False)
            r = client.get("/health", headers={"Authorization": "Bearer test"})
            assert r.status_code in (401, 503)


# ── Fix History ─────────────────────────────────────────────────────────────


class TestFixHistory:
    def test_fix_history_empty(self, api_client, api_headers):
        r = api_client.get("/fix-history", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "actions" in data
        assert "total" in data
        assert "page" in data

    def test_fix_history_pagination(self, api_client, api_headers):
        r = api_client.get("/fix-history?page=2&page_size=5", headers=api_headers)
        assert r.status_code == 200

    def test_action_detail_not_found(self, api_client, api_headers):
        r = api_client.get("/fix-history/nonexistent", headers=api_headers)
        assert r.status_code in (200, 404)

    def test_rollback_not_found(self, api_client, api_headers):
        r = api_client.post("/fix-history/nonexistent/rollback", headers=api_headers)
        assert r.status_code == 400


# ── Health & Tools ──────────────────────────────────────────────────────────


class TestHealthAndTools:
    def test_health_returns_status(self, api_client, api_headers):
        r = api_client.get("/health", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_tools_lists_modes(self, api_client, api_headers):
        r = api_client.get("/tools", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "sre" in data
        assert "security" in data


# ── Briefing & Simulate ────────────────────────────────────────────────────


class TestBriefingAndSimulate:
    def test_briefing_default(self, api_client, api_headers):
        r = api_client.get("/briefing", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "greeting" in data
        assert "summary" in data

    def test_briefing_custom_hours(self, api_client, api_headers):
        r = api_client.get("/briefing?hours=1", headers=api_headers)
        assert r.status_code == 200

    def test_simulate(self, api_client, api_headers):
        r = api_client.post("/simulate", headers=api_headers, json={"tool": "restart_deployment", "input": {}})
        assert r.status_code == 200
        data = r.json()
        assert "tool" in data
        assert "risk" in data

    def test_predictions_501(self, api_client, api_headers):
        r = api_client.get("/predictions", headers=api_headers)
        assert r.status_code == 501


# ── Monitor Control ─────────────────────────────────────────────────────────


class TestMonitorControl:
    def test_capabilities(self, api_client, api_headers):
        r = api_client.get("/monitor/capabilities", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "max_trust_level" in data

    def test_pause(self, api_client, api_headers):
        r = api_client.post("/monitor/pause", headers=api_headers)
        assert r.status_code == 200

    def test_resume(self, api_client, api_headers):
        r = api_client.post("/monitor/resume", headers=api_headers)
        assert r.status_code == 200


# ── Memory Endpoints ────────────────────────────────────────────────────────


class TestMemoryEndpoints:
    def test_memory_stats_disabled(self, api_client, api_headers):
        r = api_client.get("/memory/stats", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("enabled") is False or "incidents" in data

    def test_memory_export(self, api_client, api_headers):
        r = api_client.get("/memory/export", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "runbooks" in data
        assert "patterns" in data

    def test_memory_import(self, api_client, api_headers):
        r = api_client.post("/memory/import", headers=api_headers, json={"runbooks": [], "patterns": []})
        assert r.status_code == 200

    def test_memory_runbooks(self, api_client, api_headers):
        r = api_client.get("/memory/runbooks", headers=api_headers)
        assert r.status_code == 200

    def test_memory_incidents(self, api_client, api_headers):
        r = api_client.get("/memory/incidents", headers=api_headers)
        assert r.status_code == 200

    def test_memory_patterns(self, api_client, api_headers):
        r = api_client.get("/memory/patterns", headers=api_headers)
        assert r.status_code == 200


# ── Context & Eval ──────────────────────────────────────────────────────────


class TestContextAndEval:
    def test_context(self, api_client, api_headers):
        r = api_client.get("/context", headers=api_headers)
        assert r.status_code == 200
        data = r.json()
        assert "entries" in data

    def test_eval_status(self, api_client, api_headers):
        r = api_client.get("/eval/status", headers=api_headers)
        assert r.status_code == 200
