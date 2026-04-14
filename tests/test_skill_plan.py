"""Tests for skill plan data model."""

from __future__ import annotations

from sre_agent.skill_plan import (
    PlanResult,
    SkillOutput,
    SkillPhase,
    SkillPlan,
    topological_order,
    validate_plan,
)


class TestSkillPlanValidation:
    def test_valid_linear_plan(self):
        plan = SkillPlan(
            id="test-1",
            name="test",
            phases=[
                SkillPhase(id="triage", skill_name="sre"),
                SkillPhase(id="diagnose", skill_name="sre", depends_on=["triage"]),
                SkillPhase(id="verify", skill_name="sre", depends_on=["diagnose"]),
            ],
        )
        assert validate_plan(plan) == []

    def test_empty_plan_fails(self):
        plan = SkillPlan(id="test-2", name="empty", phases=[])
        errors = validate_plan(plan)
        assert len(errors) == 1
        assert "no phases" in errors[0]

    def test_duplicate_phase_id_fails(self):
        plan = SkillPlan(
            id="test-3",
            name="dup",
            phases=[
                SkillPhase(id="triage", skill_name="sre"),
                SkillPhase(id="triage", skill_name="security"),
            ],
        )
        errors = validate_plan(plan)
        assert any("Duplicate" in e for e in errors)

    def test_unknown_dependency_fails(self):
        plan = SkillPlan(
            id="test-4",
            name="bad-dep",
            phases=[
                SkillPhase(id="triage", skill_name="sre", depends_on=["nonexistent"]),
            ],
        )
        errors = validate_plan(plan)
        assert any("unknown phase" in e for e in errors)

    def test_cycle_detected(self):
        plan = SkillPlan(
            id="test-5",
            name="cycle",
            phases=[
                SkillPhase(id="a", skill_name="sre", depends_on=["b"]),
                SkillPhase(id="b", skill_name="sre", depends_on=["a"]),
            ],
        )
        errors = validate_plan(plan)
        assert any("Cycle" in e for e in errors)

    def test_branch_without_dependency_fails(self):
        plan = SkillPlan(
            id="test-6",
            name="bad-branch",
            phases=[
                SkillPhase(id="investigate", skill_name="sre", branch_on="root_cause"),
            ],
        )
        errors = validate_plan(plan)
        assert any("branch_on" in e for e in errors)

    def test_valid_branching_plan(self):
        plan = SkillPlan(
            id="test-7",
            name="branching",
            phases=[
                SkillPhase(id="triage", skill_name="sre", produces=["root_cause_layer"]),
                SkillPhase(
                    id="investigate",
                    skill_name="sre",
                    depends_on=["triage"],
                    branch_on="root_cause_layer",
                    branches={"database": ["db-skill"], "pod": ["pod-skill"]},
                ),
            ],
        )
        assert validate_plan(plan) == []


class TestTopologicalOrder:
    def test_linear_order(self):
        plan = SkillPlan(
            id="t-1",
            name="linear",
            phases=[
                SkillPhase(id="c", skill_name="sre", depends_on=["b"]),
                SkillPhase(id="a", skill_name="sre"),
                SkillPhase(id="b", skill_name="sre", depends_on=["a"]),
            ],
        )
        order = topological_order(plan)
        ids = [p.id for p in order]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_parallel_phases(self):
        plan = SkillPlan(
            id="t-2",
            name="parallel",
            phases=[
                SkillPhase(id="triage", skill_name="sre"),
                SkillPhase(id="db", skill_name="sre", depends_on=["triage"]),
                SkillPhase(id="pod", skill_name="sre", depends_on=["triage"]),
                SkillPhase(id="verify", skill_name="sre", depends_on=["db", "pod"]),
            ],
        )
        order = topological_order(plan)
        ids = [p.id for p in order]
        assert ids[0] == "triage"
        assert ids[-1] == "verify"
        assert set(ids[1:3]) == {"db", "pod"}


class TestSkillOutput:
    def test_default_values(self):
        output = SkillOutput(skill_id="sre", phase_id="triage")
        assert output.status == "complete"
        assert output.confidence == 0.0
        assert output.actions_taken == []

    def test_with_findings(self):
        output = SkillOutput(
            skill_id="sre",
            phase_id="diagnose",
            status="complete",
            findings={"root_cause": "db_connection_exhaustion"},
            branch_signal="database",
            confidence=0.91,
        )
        assert output.branch_signal == "database"
        assert output.findings["root_cause"] == "db_connection_exhaustion"


class TestPlanResult:
    def test_default_values(self):
        result = PlanResult(plan_id="p1", plan_name="test")
        assert result.status == "complete"
        assert result.phases_completed == 0
