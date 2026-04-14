"""Tests for postmortem generation."""

from __future__ import annotations

from sre_agent.postmortem import Postmortem, build_postmortem_context
from sre_agent.skill_plan import SkillOutput


class TestPostmortemContext:
    def test_builds_from_outputs(self):
        outputs = {
            "triage": SkillOutput(
                skill_id="sre",
                phase_id="triage",
                confidence=0.9,
                findings={"severity": "P1"},
                evidence_summary="Pod crashing",
            ),
            "diagnose": SkillOutput(
                skill_id="sre",
                phase_id="diagnose",
                confidence=0.85,
                findings={"root_cause": "OOM"},
                actions_taken=["patched memory"],
            ),
        }
        context = build_postmortem_context(outputs)
        assert "triage" in context
        assert "OOM" in context
        assert "patched memory" in context

    def test_empty_outputs(self):
        assert "No investigation" in build_postmortem_context({})

    def test_postmortem_dataclass(self):
        pm = Postmortem(id="pm-1", incident_type="crashloop", plan_id="p-1", root_cause="OOM", confidence=0.9)
        assert pm.root_cause == "OOM"
