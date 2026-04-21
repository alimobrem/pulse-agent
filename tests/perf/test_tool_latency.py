"""Performance tests — tool execution latency.

Each registered tool must execute in < 2s with mocked K8s clients.
Tests use the real tool registry to catch regressions in any tool.
"""

from __future__ import annotations

import inspect
import time
from unittest.mock import MagicMock, patch

import pytest

LATENCY_THRESHOLD_S = 2.0

_SKIP_TOOLS = frozenset(
    {
        "request_security_scan",
        "request_sre_investigation",
        "exec_command",
        "propose_git_pr",
    }
)


def _ensure_tools_loaded():
    """Import all tool modules so they register with TOOL_REGISTRY."""
    with (
        patch("sre_agent.k8s_client._initialized", True),
        patch("sre_agent.k8s_client._load_k8s"),
        patch("sre_agent.k8s_client.get_core_client", return_value=MagicMock()),
        patch("sre_agent.k8s_client.get_apps_client", return_value=MagicMock()),
        patch("sre_agent.k8s_client.get_custom_client", return_value=MagicMock()),
        patch("sre_agent.k8s_client.get_version_client", return_value=MagicMock()),
    ):
        import sre_agent.fleet_tools
        import sre_agent.git_tools
        import sre_agent.gitops_tools
        import sre_agent.handoff_tools
        import sre_agent.k8s_tools
        import sre_agent.predict_tools
        import sre_agent.security_tools
        import sre_agent.self_tools
        import sre_agent.timeline_tools
        import sre_agent.view_mutations
        import sre_agent.view_tools  # noqa: F401


_ensure_tools_loaded()

from sre_agent.tool_registry import TOOL_REGISTRY


def _make_mock_k8s():
    core = MagicMock()
    core.list_namespaced_pod.return_value = MagicMock(items=[])
    core.list_node.return_value = MagicMock(items=[])
    core.list_namespaced_service.return_value = MagicMock(items=[])
    core.list_namespaced_event.return_value = MagicMock(items=[])
    core.list_namespaced_config_map.return_value = MagicMock(items=[])
    core.list_namespaced_secret.return_value = MagicMock(items=[])
    core.read_namespaced_pod_log.return_value = ""

    apps = MagicMock()
    apps.list_namespaced_deployment.return_value = MagicMock(items=[])
    apps.list_namespaced_stateful_set.return_value = MagicMock(items=[])
    apps.list_namespaced_daemon_set.return_value = MagicMock(items=[])

    custom = MagicMock()
    custom.list_cluster_custom_object.return_value = {"items": []}
    custom.list_namespaced_custom_object.return_value = {"items": []}

    return core, apps, custom


def _get_testable_tools() -> list[str]:
    return [name for name in TOOL_REGISTRY if name not in _SKIP_TOOLS]


class TestToolLatency:
    def test_tool_registry_loaded(self):
        assert len(TOOL_REGISTRY) >= 90, f"Expected 90+ tools, got {len(TOOL_REGISTRY)}"

    @pytest.mark.parametrize("tool_name", _get_testable_tools())
    def test_tool_executes_within_threshold(self, tool_name):
        core, apps, custom = _make_mock_k8s()

        with (
            patch("sre_agent.k8s_client._initialized", True),
            patch("sre_agent.k8s_client._load_k8s"),
            patch("sre_agent.k8s_client.get_core_client", return_value=core),
            patch("sre_agent.k8s_client.get_apps_client", return_value=apps),
            patch("sre_agent.k8s_client.get_custom_client", return_value=custom),
            patch("sre_agent.k8s_client.get_version_client", return_value=MagicMock()),
        ):
            tool = TOOL_REGISTRY[tool_name]
            fn = tool.function if hasattr(tool, "function") else tool

            sig = inspect.signature(fn)
            kwargs: dict = {}
            for param_name, param in sig.parameters.items():
                if param.default is not inspect.Parameter.empty:
                    continue
                if param_name in ("namespace", "ns"):
                    kwargs[param_name] = "default"
                elif param_name in ("name", "deployment", "pod", "service"):
                    kwargs[param_name] = "test-resource"
                elif param_name == "query":
                    kwargs[param_name] = "up"
                elif param_name == "resource_type":
                    kwargs[param_name] = "pods"
                elif param_name == "kind":
                    kwargs[param_name] = "Pod"
                elif param_name == "title":
                    kwargs[param_name] = "Test"
                else:
                    kwargs[param_name] = "test"

            start = time.monotonic()
            try:
                fn(**kwargs)
            except Exception:
                pass
            elapsed = time.monotonic() - start

            assert elapsed < LATENCY_THRESHOLD_S, (
                f"Tool '{tool_name}' took {elapsed:.2f}s (threshold: {LATENCY_THRESHOLD_S}s)"
            )
