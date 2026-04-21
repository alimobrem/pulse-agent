"""Tests for skill conflict resolution — ensures conflicting skills don't run in parallel."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _setup():
    with (
        patch("sre_agent.k8s_client._initialized", True),
        patch("sre_agent.k8s_client._load_k8s"),
        patch("sre_agent.k8s_client.get_core_client", return_value=MagicMock()),
    ):
        from sre_agent.skill_loader import load_skills

        load_skills()


_setup()


class TestExclusiveSkills:
    """Exclusive skills never get a secondary — they own the full request lifecycle."""

    def test_view_designer_is_exclusive(self):
        from sre_agent.skill_loader import get_skill

        vd = get_skill("view_designer")
        assert vd is not None
        assert vd.exclusive is True

    def test_postmortem_is_exclusive(self):
        from sre_agent.skill_loader import get_skill

        pm = get_skill("postmortem")
        assert pm is not None
        assert pm.exclusive is True

    def test_sre_is_not_exclusive(self):
        from sre_agent.skill_loader import get_skill

        sre = get_skill("sre")
        assert sre is not None
        assert sre.exclusive is False

    def test_exclusive_skill_never_gets_secondary(self):
        from sre_agent.skill_router import classify_query_multi

        primary, secondary = classify_query_multi("Create a dashboard showing node health: CPU/memory utilization")
        assert primary.name == "view_designer"
        assert secondary is None, f"Exclusive skill got secondary={secondary.name if secondary else None}"

    def test_exclusive_add_widget(self):
        from sre_agent.skill_router import classify_query_multi

        primary, secondary = classify_query_multi("Add a memory chart to the dashboard")
        assert primary.name == "view_designer"
        assert secondary is None


class TestConflictsWithBidirectional:
    """conflicts_with is checked in both directions."""

    def test_view_designer_conflicts_with_plan_builder(self):
        from sre_agent.skill_loader import get_skill

        vd = get_skill("view_designer")
        assert vd is not None
        assert "plan-builder" in vd.conflicts_with

    def test_bidirectional_check(self):
        from sre_agent.skill_router import _skills_conflict

        class FakeSkill:
            def __init__(self, name, conflicts):
                self.name = name
                self.conflicts_with = conflicts

        a = FakeSkill("view_designer", ["plan-builder"])
        b = FakeSkill("plan-builder", [])
        assert _skills_conflict(a, b) is True
        assert _skills_conflict(b, a) is True

        c = FakeSkill("sre", [])
        d = FakeSkill("security", [])
        assert _skills_conflict(c, d) is False


class TestNonConflictingMultiSkill:
    """Non-exclusive, non-conflicting skills CAN run in parallel."""

    def test_sre_security_can_run_together(self):
        from sre_agent.skill_router import classify_query_multi

        primary, secondary = classify_query_multi("check for crashlooping pods and scan RBAC vulnerabilities")
        if secondary:
            assert primary.name != secondary.name
