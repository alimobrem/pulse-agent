"""WebSocket integration tests for /ws/sre, /ws/agent, /ws/monitor endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def pulse_token():
    return "test-ws-token-xyz"


@pytest.fixture
def ws_client(pulse_token, monkeypatch, tmp_path):
    monkeypatch.setenv("PULSE_AGENT_WS_TOKEN", pulse_token)
    monkeypatch.setenv("PULSE_AGENT_MEMORY", "0")
    # PULSE_AGENT_DATABASE_URL set by conftest autouse fixture

    with (
        patch("sre_agent.k8s_client._initialized", True),
        patch("sre_agent.k8s_client._load_k8s"),
        patch("sre_agent.k8s_tools.get_core_client", return_value=MagicMock()),
        patch("sre_agent.k8s_tools.get_apps_client", return_value=MagicMock()),
        patch("sre_agent.k8s_tools.get_custom_client", return_value=MagicMock()),
        patch("sre_agent.k8s_tools.get_version_client", return_value=MagicMock()),
    ):
        from sre_agent.api import app

        yield TestClient(app)


# ── Auth ────────────────────────────────────────────────────────────────────


class TestWebSocketAuth:
    def test_sre_rejects_no_token(self, ws_client):
        with pytest.raises((WebSocketDisconnect, Exception)), ws_client.websocket_connect("/ws/sre"):
            pass

    def test_sre_rejects_wrong_token(self, ws_client):
        with pytest.raises((WebSocketDisconnect, Exception)), ws_client.websocket_connect("/ws/sre?token=wrong"):
            pass

    def test_sre_accepts_valid_token(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/sre?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] == "cleared"

    def test_invalid_mode_rejected(self, ws_client, pulse_token):
        with (
            pytest.raises((WebSocketDisconnect, Exception)),
            ws_client.websocket_connect(f"/ws/invalid?token={pulse_token}"),
        ):
            pass

    def test_security_mode_connects(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/security?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] == "cleared"


# ── Protocol ────────────────────────────────────────────────────────────────


class TestWebSocketProtocol:
    def test_clear_resets_conversation(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/sre?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] == "cleared"

    def test_invalid_json_returns_error(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/sre?token={pulse_token}") as ws:
            ws.send_text("not json at all")
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Invalid JSON" in data["message"]

    def test_feedback_returns_ack(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/sre?token={pulse_token}") as ws:
            ws.send_json({"type": "feedback", "resolved": True})
            data = ws.receive_json()
            assert data["type"] == "feedback_ack"
            assert data["resolved"] is True
            assert "score" in data

    def test_feedback_with_message_id(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/sre?token={pulse_token}") as ws:
            ws.send_json({"type": "feedback", "resolved": False, "messageId": "msg-123"})
            data = ws.receive_json()
            assert data["type"] == "feedback_ack"
            assert data["resolved"] is False

    def test_message_triggers_agent_response(self, ws_client, pulse_token):
        """Send a message and verify we get at least a done or error event back."""
        with (
            patch("sre_agent.api.run_agent_streaming", return_value="Test response"),
            patch("sre_agent.api.create_client", return_value=MagicMock()),
            ws_client.websocket_connect(f"/ws/sre?token={pulse_token}") as ws,
        ):
            ws.send_json({"type": "message", "content": "hello"})
            events = []
            for _ in range(20):
                try:
                    data = ws.receive_json(mode="text")
                    events.append(data)
                    if data["type"] in ("done", "error"):
                        break
                except Exception:
                    break
            assert len(events) > 0
            last = events[-1]
            assert last["type"] in ("done", "error")


# ── Auto-Agent ──────────────────────────────────────────────────────────────


class TestAutoAgent:
    def test_agent_mode_connects(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "clear"})
            data = ws.receive_json()
            assert data["type"] == "cleared"

    def test_agent_mode_feedback(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/agent?token={pulse_token}") as ws:
            ws.send_json({"type": "feedback", "resolved": True})
            data = ws.receive_json()
            assert data["type"] == "feedback_ack"


# ── Monitor ─────────────────────────────────────────────────────────────────


class TestMonitorWebSocket:
    def test_monitor_connects(self, ws_client, pulse_token):
        with ws_client.websocket_connect(f"/ws/monitor?token={pulse_token}") as ws:
            ws.send_json(
                {
                    "type": "subscribe_monitor",
                    "trustLevel": 1,
                    "autoFixCategories": [],
                }
            )
            ws.close()

    def test_monitor_rejects_no_token(self, ws_client):
        with pytest.raises((WebSocketDisconnect, Exception)), ws_client.websocket_connect("/ws/monitor"):
            pass
