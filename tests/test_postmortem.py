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

    def test_context_includes_risk_flags(self):
        outputs = {
            "diagnose": SkillOutput(
                skill_id="sre",
                phase_id="diagnose",
                confidence=0.7,
                risk_flags=["data loss risk", "cascading failure"],
            ),
        }
        context = build_postmortem_context(outputs)
        assert "data loss risk" in context
        assert "cascading failure" in context

    def test_context_includes_open_questions(self):
        outputs = {
            "triage": SkillOutput(
                skill_id="sre",
                phase_id="triage",
                confidence=0.6,
                open_questions=["Was there a recent deploy?"],
            ),
        }
        context = build_postmortem_context(outputs)
        assert "recent deploy" in context

    def test_postmortem_defaults(self):
        pm = Postmortem(id="pm-2", incident_type="oom", plan_id="p-2")
        assert pm.root_cause == ""
        assert pm.contributing_factors == []
        assert pm.blast_radius == []
        assert pm.confidence == 0.0

    def test_context_truncates_large_findings(self):
        outputs = {
            "scan": SkillOutput(
                skill_id="security",
                phase_id="scan",
                confidence=0.95,
                findings={f"finding_{i}": f"value_{i}" for i in range(20)},
            ),
        }
        context = build_postmortem_context(outputs)
        assert "finding_7" in context
        assert "finding_8" not in context
