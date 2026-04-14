"""Tests for skill auto-scaffolding."""

from __future__ import annotations

from sre_agent.skill_scaffolder import scaffold_skill_from_resolution


class TestScaffoldSkill:
    def test_generates_valid_skill(self):
        content = scaffold_skill_from_resolution(
            query="pods crashing due to OOM in production",
            tools_called=["describe_pod", "get_pod_logs", "get_events"],
            investigation_summary="Container exceeded 256Mi memory limit",
            root_cause="OOM at 256Mi limit",
            confidence=0.91,
        )
        assert "name:" in content
        assert "keywords:" in content
        assert "OOM" in content
        assert "describe_pod" in content

    def test_handles_empty_tools(self):
        content = scaffold_skill_from_resolution(
            query="unknown issue",
            tools_called=[],
            investigation_summary="unclear",
            root_cause="unknown",
            confidence=0.3,
        )
        assert "name:" in content

    def test_includes_confidence(self):
        content = scaffold_skill_from_resolution(
            query="test",
            tools_called=["list_pods"],
            investigation_summary="test",
            root_cause="test",
            confidence=0.85,
        )
        assert "85%" in content
