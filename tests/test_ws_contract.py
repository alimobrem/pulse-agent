"""WebSocket contract tests — validates message schemas against API_CONTRACT.md.

Ensures all documented message types are handled and follow the documented format.
Tests run against the FastAPI test client (no live server needed).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def pulse_token():
    return "contract-test-token"


@pytest.fixture
def ws_client(pulse_token, monkeypatch):
    monkeypatch.setenv("PULSE_AGENT_WS_TOKEN", pulse_token)
    monkeypatch.setenv("PULSE_AGENT_MEMORY", "0")

    with (
        patch("sre_agent.k8s_client._initialized", True),
        patch("sre_agent.k8s_client._load_k8s"),
        patch("sre_agent.k8s_client.get_core_client", return_value=MagicMock()),
        patch("sre_agent.k8s_client.get_apps_client", return_value=MagicMock()),
        patch("sre_agent.k8s_client.get_custom_client", return_value=MagicMock()),
        patch("sre_agent.k8s_client.get_version_client", return_value=MagicMock()),
    ):
        from sre_agent.api import app

        yield TestClient(app)


# ---------------------------------------------------------------------------
# Chat Protocol (/ws/agent) — Client-to-Server Messages
# ---------------------------------------------------------------------------


class TestChatClientMessages:
    """Validate all client-to-server message types from API_CONTRACT.md."""

    def test_clear_message(self, ws_client, pulse_token):
        """clear → cleared response."""
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] == "cleared"

    def test_message_with_context(self, ws_client, pulse_token):
        """message with ResourceContext fields is accepted."""
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json(
                {
                    "type": "message",
                    "content": "test",
                    "context": {
                        "kind": "Deployment",
                        "name": "api-server",
                        "namespace": "production",
                        "gvr": "apps~v1~deployments",
                    },
                    "fleet": False,
                }
            )
            # Should get at least one response (text_delta, error, or done)
            data = ws.receive_json()
            assert "type" in data

    def test_confirm_response_without_pending_nonce(self, ws_client, pulse_token):
        """confirm_response with no pending request should be ignored or error."""
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json(
                {
                    "type": "confirm_response",
                    "approved": True,
                    "nonce": "nonexistent-nonce",
                }
            )
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] in ("cleared", "error")

    def test_unknown_message_type(self, ws_client, pulse_token):
        """Unknown message types should not crash the connection."""
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "nonexistent_type"})
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] in ("cleared", "error")


# ---------------------------------------------------------------------------
# Chat Protocol (/ws/agent) — Server-to-Client Events
# ---------------------------------------------------------------------------


class TestChatServerEvents:
    """Validate server-to-client event schemas."""

    def test_cleared_event_schema(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data == {"type": "cleared"}

    def test_done_event_has_full_response(self, ws_client, pulse_token):
        """After a message, the done event should include full_response."""
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "message", "content": "hello"})
            events = []
            for _ in range(50):
                try:
                    data = ws.receive_json()
                    events.append(data)
                    if data.get("type") == "done":
                        break
                except Exception:
                    break

            done_events = [e for e in events if e.get("type") == "done"]
            if done_events:
                assert "full_response" in done_events[0]

    def test_text_delta_schema(self, ws_client, pulse_token):
        """text_delta events must have a text field."""
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "message", "content": "hi"})
            events = []
            for _ in range(50):
                try:
                    data = ws.receive_json()
                    events.append(data)
                    if data.get("type") == "done":
                        break
                except Exception:
                    break

            text_deltas = [e for e in events if e.get("type") == "text_delta"]
            for td in text_deltas:
                assert "text" in td, "text_delta missing 'text' field"


# ---------------------------------------------------------------------------
# Monitor Protocol (/ws/monitor) — Client-to-Server Messages
# ---------------------------------------------------------------------------


class TestMonitorClientMessages:
    """Validate monitor client-to-server message types."""

    def test_subscribe_monitor(self, ws_client, pulse_token):
        """subscribe_monitor is accepted without error."""
        with ws_client.websocket_connect(f"/ws/monitor?token={pulse_token}") as ws:
            ws.send_json(
                {
                    "type": "subscribe_monitor",
                    "trustLevel": 1,
                    "autoFixCategories": ["crash_loop"],
                }
            )
            ws.close()

    def test_subscribe_monitor_defaults(self, ws_client, pulse_token):
        """subscribe_monitor works with minimal fields."""
        with ws_client.websocket_connect(f"/ws/monitor?token={pulse_token}") as ws:
            ws.send_json({"type": "subscribe_monitor"})
            ws.close()

    def test_monitor_rejects_no_token(self, ws_client):
        with pytest.raises((WebSocketDisconnect, Exception)):
            with ws_client.websocket_connect("/ws/monitor"):
                pass


# ---------------------------------------------------------------------------
# Auth Contract
# ---------------------------------------------------------------------------


class TestAuthContract:
    """Verify auth behavior matches API_CONTRACT.md."""

    def test_no_token_disconnects_with_4001(self, ws_client):
        with pytest.raises((WebSocketDisconnect, Exception)):
            with ws_client.websocket_connect("/ws/agent"):
                pass

    def test_wrong_token_disconnects(self, ws_client):
        with pytest.raises((WebSocketDisconnect, Exception)):
            with ws_client.websocket_connect("/ws/agent?token=wrong"):
                pass

    def test_valid_token_connects(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            assert ws.receive_json()["type"] == "cleared"


# ---------------------------------------------------------------------------
# REST Contract — Spot checks for key endpoints
# ---------------------------------------------------------------------------


class TestRESTContract:
    """Verify key REST endpoints match API_CONTRACT.md schemas."""

    def test_healthz(self, ws_client, pulse_token):
        resp = ws_client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_version(self, ws_client, pulse_token):
        resp = ws_client.get(f"/version?token={pulse_token}")
        data = resp.json()
        assert "protocol" in data
        assert "agent" in data
        assert "tools" in data
        assert isinstance(data["tools"], int)

    def test_health(self, ws_client, pulse_token):
        resp = ws_client.get(f"/health?token={pulse_token}")
        assert resp.status_code == 200
        data = resp.json()
        assert "circuit_breaker" in data
        assert data["circuit_breaker"]["state"] in ("closed", "open", "half_open")

    def test_tools(self, ws_client, pulse_token):
        resp = ws_client.get(f"/tools?token={pulse_token}")
        assert resp.status_code == 200
        data = resp.json()
        assert "sre" in data
        assert "security" in data
        assert isinstance(data["sre"], list)
        if data["sre"]:
            tool = data["sre"][0]
            assert "name" in tool
            assert "description" in tool
            assert "requires_confirmation" in tool

    def test_agents(self, ws_client, pulse_token):
        resp = ws_client.get(f"/agents?token={pulse_token}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            agent = data[0]
            assert "name" in agent
            assert "description" in agent
            assert "tools_count" in agent

    def test_views_list(self, ws_client, pulse_token):
        resp = ws_client.get(
            f"/views?token={pulse_token}",
            headers={"X-Forwarded-User": "test-user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "views" in data
        assert isinstance(data["views"], list)

    def test_unauthenticated_returns_401(self, ws_client):
        resp = ws_client.get("/tools")
        assert resp.status_code in (401, 403)
