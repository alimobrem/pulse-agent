"""Tests for action_button sanitization in _sanitize_components."""

from __future__ import annotations

from sre_agent.api.sanitize import _sanitize_components


class TestActionButtonSanitization:
    def test_valid_action_button_preserved(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Scale Up",
                "action": "scale_deployment",
                "action_input": {"name": "nginx", "namespace": "default", "replicas": 3},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 1
        assert result[0]["kind"] == "action_button"
        assert result[0]["_is_write"] is True

    def test_blocked_tool_stripped(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Drain",
                "action": "drain_node",
                "action_input": {"node_name": "worker-1"},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 0

    def test_exec_command_blocked(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Exec",
                "action": "exec_command",
                "action_input": {"command": "ls"},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 0

    def test_unknown_tool_stripped(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Go",
                "action": "nonexistent_tool_xyz",
                "action_input": {},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 0

    def test_invalid_namespace_stripped(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Scale",
                "action": "scale_deployment",
                "action_input": {"name": "nginx", "namespace": "INVALID-NS!!"},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 0

    def test_replicas_out_of_range_stripped(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Scale",
                "action": "scale_deployment",
                "action_input": {"name": "nginx", "namespace": "default", "replicas": 999},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 0

    def test_read_tool_not_flagged_as_write(self):
        comps = [
            {
                "kind": "action_button",
                "label": "List Pods",
                "action": "list_pods",
                "action_input": {"namespace": "default"},
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 1
        assert result[0].get("_is_write") is False

    def test_other_components_unchanged(self):
        comps = [
            {"kind": "metric_card", "title": "CPU", "value": "72%"},
            {
                "kind": "action_button",
                "label": "Go",
                "action": "drain_node",
                "action_input": {},
            },
            {"kind": "status_list", "title": "Alerts", "items": []},
        ]
        result = _sanitize_components(comps)
        assert len(result) == 2
        assert result[0]["kind"] == "metric_card"
        assert result[1]["kind"] == "status_list"

    def test_nested_in_grid(self):
        comps = [
            {
                "kind": "grid",
                "items": [
                    {
                        "kind": "action_button",
                        "label": "Drain",
                        "action": "drain_node",
                        "action_input": {},
                    },
                    {"kind": "metric_card", "title": "CPU", "value": "50%"},
                ],
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 1
        assert result[0]["kind"] == "grid"
        assert len(result[0]["items"]) == 1
        assert result[0]["items"][0]["kind"] == "metric_card"

    def test_action_input_not_dict_stripped(self):
        comps = [
            {
                "kind": "action_button",
                "label": "Go",
                "action": "list_pods",
                "action_input": "not a dict",
            }
        ]
        result = _sanitize_components(comps)
        assert len(result) == 0
