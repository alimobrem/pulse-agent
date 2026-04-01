"""Tests for serve.py — API server startup, socket cleanup, signal handling."""

from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock, patch

import pytest

from sre_agent.serve import _cleanup_socket, _signal_handler, main


class TestCleanupSocket:
    def test_removes_socket_file(self, tmp_path):
        sock = tmp_path / "agent.sock"
        sock.touch()
        with patch.dict(os.environ, {"PULSE_AGENT_SOCKET": str(sock)}):
            _cleanup_socket()
        assert not sock.exists()

    def test_no_socket_env_is_noop(self):
        with patch.dict(os.environ, {"PULSE_AGENT_SOCKET": ""}, clear=False):
            _cleanup_socket()  # Should not raise

    def test_missing_socket_file_is_noop(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent.sock")
        with patch.dict(os.environ, {"PULSE_AGENT_SOCKET": fake_path}):
            _cleanup_socket()  # Should not raise

    def test_os_error_on_socket_unlink_is_swallowed(self, tmp_path):
        sock = tmp_path / "agent.sock"
        sock.touch()
        with (
            patch.dict(os.environ, {"PULSE_AGENT_SOCKET": str(sock)}),
            patch("sre_agent.serve.os.unlink", side_effect=OSError("permission denied")),
        ):
            _cleanup_socket()  # Should not raise


class TestSignalHandler:
    def test_signal_handler_calls_cleanup_and_exits(self):
        with (
            patch("sre_agent.serve._cleanup_socket") as mock_cleanup,
            pytest.raises(SystemExit) as exc_info,
        ):
            _signal_handler(signal.SIGTERM, None)
        mock_cleanup.assert_called_once()
        assert exc_info.value.code == 0


class TestMain:
    def test_tcp_mode(self):
        with (
            patch("sre_agent.config.validate_config"),
            patch("sre_agent.serve.atexit.register"),
            patch("sre_agent.serve.signal.signal"),
            patch("sre_agent.serve._cleanup_socket"),
            patch("sre_agent.serve.uvicorn.run") as mock_run,
            patch.dict(
                os.environ, {"PULSE_AGENT_HOST": "127.0.0.1", "PULSE_AGENT_PORT": "9090", "PULSE_AGENT_SOCKET": ""}
            ),
            patch("builtins.open", MagicMock()),
        ):
            main()
            mock_run.assert_called_once_with("sre_agent.api:app", host="127.0.0.1", port=9090, log_level="info")

    def test_unix_socket_mode(self, tmp_path):
        sock_path = str(tmp_path / "test.sock")
        with (
            patch("sre_agent.config.validate_config"),
            patch("sre_agent.serve.atexit.register"),
            patch("sre_agent.serve.signal.signal"),
            patch("sre_agent.serve._cleanup_socket"),
            patch("sre_agent.serve.uvicorn.run") as mock_run,
            patch.dict(os.environ, {"PULSE_AGENT_SOCKET": sock_path}),
            patch("builtins.open", MagicMock()),
        ):
            main()
            mock_run.assert_called_once_with("sre_agent.api:app", uds=sock_path, log_level="info")
