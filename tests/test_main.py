"""Tests for main.py — CLI entry point, banner, confirm action, REPL commands."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sre_agent.main import (
    HELP_TEXT,
    MODES,
    _confirm_action,
    main,
    print_banner,
    run_repl,
)


class TestConfirmAction:
    def test_confirm_yes(self):
        with patch("sre_agent.main.console") as mock_console:
            mock_console.input.return_value = "y"
            assert asyncio.run(_confirm_action("delete_pod", {"pod_name": "x"})) is True

    def test_confirm_yes_full(self):
        with patch("sre_agent.main.console") as mock_console:
            mock_console.input.return_value = "yes"
            assert asyncio.run(_confirm_action("delete_pod", {})) is True

    def test_confirm_no(self):
        with patch("sre_agent.main.console") as mock_console:
            mock_console.input.return_value = "n"
            assert asyncio.run(_confirm_action("delete_pod", {})) is False

    def test_confirm_empty(self):
        with patch("sre_agent.main.console") as mock_console:
            mock_console.input.return_value = ""
            assert asyncio.run(_confirm_action("delete_pod", {})) is False

    def test_confirm_eof(self):
        with patch("sre_agent.main.console") as mock_console:
            mock_console.input.side_effect = EOFError
            assert asyncio.run(_confirm_action("delete_pod", {})) is False

    def test_confirm_keyboard_interrupt(self):
        with patch("sre_agent.main.console") as mock_console:
            mock_console.input.side_effect = KeyboardInterrupt
            assert asyncio.run(_confirm_action("delete_pod", {})) is False


class TestModes:
    def test_sre_mode_exists(self):
        assert "sre" in MODES
        assert "banner" in MODES["sre"]
        assert "runner" in MODES["sre"]
        assert MODES["sre"]["prompt"] == "sre"

    def test_security_mode_exists(self):
        assert "security" in MODES
        assert "banner" in MODES["security"]
        assert MODES["security"]["prompt"] == "sec"

    def test_help_text_has_examples(self):
        assert "SRE Examples" in HELP_TEXT
        assert "Security Examples" in HELP_TEXT
        assert "help" in HELP_TEXT


class TestPrintBanner:
    def test_print_sre_banner(self):
        with patch("sre_agent.main.console") as mock_console:
            print_banner("sre", memory_active=False)
            mock_console.print.assert_called_once()

    def test_print_banner_with_memory(self):
        with patch("sre_agent.main.console") as mock_console:
            print_banner("sre", memory_active=True)
            args = mock_console.print.call_args
            # The Panel object should contain "memory active" in its renderable
            panel = args[0][0]
            assert "memory active" in panel.renderable


class TestRunRepl:
    def _run_repl_with_inputs(self, inputs, mode="sre"):
        """Run the REPL with a sequence of user inputs."""
        mock_console = MagicMock()
        mock_console.input.side_effect = inputs
        with (
            patch("sre_agent.main.console", mock_console),
            patch("sre_agent.memory.is_memory_enabled", return_value=False),
            patch("sre_agent.main.create_async_client", return_value=MagicMock()),
            patch("sre_agent.k8s_client.get_core_client") as mock_k8s,
        ):
            mock_k8s.return_value.list_namespace.return_value = MagicMock()
            return asyncio.run(run_repl(mode)), mock_console

    def test_quit_command(self):
        result, _ = self._run_repl_with_inputs(["quit"])
        assert result == "quit"

    def test_exit_command(self):
        result, _ = self._run_repl_with_inputs(["exit"])
        assert result == "quit"

    def test_q_command(self):
        result, _ = self._run_repl_with_inputs(["q"])
        assert result == "quit"

    def test_mode_switch(self):
        result, _ = self._run_repl_with_inputs(["mode"])
        assert result == "switch"

    def test_clear_command(self):
        result, _ = self._run_repl_with_inputs(["clear", "quit"])
        assert result == "quit"

    def test_help_command(self):
        result, _console = self._run_repl_with_inputs(["help", "quit"])
        assert result == "quit"

    def test_empty_input_skipped(self):
        result, _ = self._run_repl_with_inputs(["", "quit"])
        assert result == "quit"

    def test_eof_exits_gracefully(self):
        mock_console = MagicMock()
        mock_console.input.side_effect = [EOFError]
        with (
            patch("sre_agent.main.console", mock_console),
            patch("sre_agent.memory.is_memory_enabled", return_value=False),
            patch("sre_agent.main.create_async_client", return_value=MagicMock()),
            patch("sre_agent.k8s_client.get_core_client") as mock_k8s,
        ):
            mock_k8s.return_value.list_namespace.return_value = MagicMock()
            result = asyncio.run(run_repl("sre"))
        assert result == "quit"

    def test_client_init_failure_exits(self):
        with (
            patch("sre_agent.main.console"),
            patch("sre_agent.memory.is_memory_enabled", return_value=False),
            patch("sre_agent.main.create_async_client", side_effect=RuntimeError("no key")),
            pytest.raises(SystemExit),
        ):
            asyncio.run(run_repl("sre"))

    def test_feedback_no_previous_interaction(self):
        result, _ = self._run_repl_with_inputs(["feedback", "quit"])
        assert result == "quit"


class TestMainEntrypoint:
    def test_default_sre_mode(self):
        mock_repl = AsyncMock(return_value="quit")
        with (
            patch("sre_agent.main.run_repl", mock_repl),
            patch.object(sys, "argv", ["main.py"]),
        ):
            main()
            mock_repl.assert_called_once_with("sre")

    def test_security_mode_from_argv(self):
        mock_repl = AsyncMock(return_value="quit")
        with (
            patch("sre_agent.main.run_repl", mock_repl),
            patch.object(sys, "argv", ["main.py", "security"]),
        ):
            main()
            mock_repl.assert_called_once_with("security")

    def test_mode_switch_loop(self):
        mock_repl = AsyncMock(side_effect=["switch", "quit"])
        with (
            patch("sre_agent.main.run_repl", mock_repl),
            patch.object(sys, "argv", ["main.py"]),
        ):
            main()
            assert mock_repl.call_count == 2
            mock_repl.assert_any_call("sre")
            mock_repl.assert_any_call("security")

    def test_invalid_mode_ignored(self):
        mock_repl = AsyncMock(return_value="quit")
        with (
            patch("sre_agent.main.run_repl", mock_repl),
            patch.object(sys, "argv", ["main.py", "invalid"]),
        ):
            main()
            mock_repl.assert_called_once_with("sre")
