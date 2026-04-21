"""Tests for status_pipeline component validation and view layout templates."""

from __future__ import annotations

from sre_agent.component_registry import COMPONENT_REGISTRY, get_component
from sre_agent.layout_engine import build_view_layout
from sre_agent.quality_engine import QualityResult, _validate_component


def _validate(comp: dict) -> QualityResult:
    result = QualityResult()
    _validate_component(comp, result)
    return result


class TestStatusPipelineRegistry:
    def test_registered(self):
        assert "status_pipeline" in COMPONENT_REGISTRY

    def test_category(self):
        c = get_component("status_pipeline")
        assert c is not None
        assert c.category == "status"

    def test_title_not_required(self):
        c = get_component("status_pipeline")
        assert c is not None
        assert c.title_required is False

    def test_required_fields(self):
        c = get_component("status_pipeline")
        assert c is not None
        assert "steps" in c.required_fields
        assert "current" in c.required_fields


class TestStatusPipelineValidation:
    def test_valid(self):
        r = _validate({"kind": "status_pipeline", "steps": ["A", "B", "C"], "current": 1})
        assert not r.errors

    def test_valid_at_first_step(self):
        r = _validate({"kind": "status_pipeline", "steps": ["X", "Y"], "current": 0})
        assert not r.errors

    def test_valid_at_last_step(self):
        r = _validate({"kind": "status_pipeline", "steps": ["X", "Y", "Z"], "current": 2})
        assert not r.errors

    def test_missing_steps(self):
        r = _validate({"kind": "status_pipeline", "current": 0})
        assert any("steps" in e for e in r.errors)

    def test_empty_steps(self):
        r = _validate({"kind": "status_pipeline", "steps": [], "current": 0})
        assert any("steps" in e for e in r.errors)

    def test_single_step_rejected(self):
        r = _validate({"kind": "status_pipeline", "steps": ["Only"], "current": 0})
        assert any("at least 2" in e for e in r.errors)

    def test_missing_current(self):
        r = _validate({"kind": "status_pipeline", "steps": ["A", "B"]})
        assert any("current" in e for e in r.errors)

    def test_current_negative(self):
        r = _validate({"kind": "status_pipeline", "steps": ["A", "B"], "current": -1})
        assert any("current" in e for e in r.errors)

    def test_current_out_of_range(self):
        r = _validate({"kind": "status_pipeline", "steps": ["A", "B"], "current": 2})
        assert any("current" in e for e in r.errors)

    def test_current_string_rejected(self):
        r = _validate({"kind": "status_pipeline", "steps": ["A", "B"], "current": "1"})
        assert any("current" in e for e in r.errors)


class TestBuildViewLayoutIncident:
    def test_custom_view_passthrough(self):
        components = [{"kind": "metric_card", "title": "CPU", "value": "42%"}]
        result = build_view_layout(components, "custom")
        assert result is components

    def test_incident_creates_hero_and_tabs(self):
        components = [
            {"kind": "confidence_badge", "score": 0.85},
            {"kind": "metric_card", "title": "Restarts", "value": "12"},
            {"kind": "resolution_tracker", "steps": [{"title": "Fix", "status": "done", "detail": "ok"}]},
            {
                "kind": "blast_radius",
                "items": [
                    {
                        "kind_abbrev": "Svc",
                        "name": "api",
                        "relationship": "targets",
                        "status": "degraded",
                        "status_detail": "0 endpoints",
                    }
                ],
            },
            {"kind": "timeline", "lanes": []},
        ]
        result = build_view_layout(components, "incident", "investigating")
        assert len(result) == 2
        hero = result[0]
        tabs = result[1]

        assert hero["kind"] == "section"
        assert hero["collapsible"] is False
        hero_children = hero["components"]
        assert hero_children[0]["kind"] == "confidence_badge"
        assert hero_children[1]["kind"] == "status_pipeline"
        assert hero_children[1]["current"] == 1  # investigating
        assert hero_children[2]["kind"] == "grid"

        assert tabs["kind"] == "tabs"
        tab_labels = [t["label"] for t in tabs["tabs"]]
        assert tab_labels == ["Resolution", "Analysis", "Impact", "Timeline"]
        assert any(c["kind"] == "resolution_tracker" for c in tabs["tabs"][0]["components"])
        assert any(c["kind"] == "blast_radius" for c in tabs["tabs"][2]["components"])
        assert any(c["kind"] == "timeline" for c in tabs["tabs"][3]["components"])

    def test_incident_status_pipeline_step_mapping(self):
        components = [{"kind": "data_table", "columns": []}]
        for status, expected_step in [("investigating", 1), ("action_taken", 2), ("verifying", 3), ("resolved", 4)]:
            result = build_view_layout(components, "incident", status)
            pipeline = result[0]["components"][0]
            assert pipeline["kind"] == "status_pipeline"
            assert pipeline["current"] == expected_step, f"status={status}"

    def test_analysis_tab_gets_key_value_and_tables(self):
        components = [
            {"kind": "key_value", "pairs": [{"key": "Root Cause", "value": "OOM"}]},
            {"kind": "data_table", "columns": [{"id": "pod", "header": "Pod"}]},
        ]
        result = build_view_layout(components, "incident")
        analysis_tab = result[1]["tabs"][1]
        assert analysis_tab["label"] == "Analysis"
        assert len(analysis_tab["components"]) == 2


class TestBuildViewLayoutPlan:
    def test_plan_tabs(self):
        components = [{"kind": "resolution_tracker", "steps": []}]
        result = build_view_layout(components, "plan", "ready")
        tabs = result[1]
        tab_labels = [t["label"] for t in tabs["tabs"]]
        assert tab_labels == ["Prerequisites", "Steps", "Impact", "Current State"]

    def test_plan_status_steps(self):
        components = []
        result = build_view_layout(components, "plan", "executing")
        pipeline = result[0]["components"][0]
        assert pipeline["steps"] == ["Analyzing", "Ready", "Executing", "Completed"]
        assert pipeline["current"] == 2


class TestBuildViewLayoutAssessment:
    def test_assessment_tabs(self):
        components = []
        result = build_view_layout(components, "assessment", "acknowledged")
        tabs = result[1]
        tab_labels = [t["label"] for t in tabs["tabs"]]
        assert tab_labels == ["Trend", "Recommendations", "Impact"]
        pipeline = result[0]["components"][0]
        assert pipeline["current"] == 2

    def test_assessment_blast_radius_in_impact(self):
        components = [
            {"kind": "blast_radius", "items": []},
        ]
        result = build_view_layout(components, "assessment")
        impact_tab = result[1]["tabs"][2]
        assert impact_tab["label"] == "Impact"
        assert any(c["kind"] == "blast_radius" for c in impact_tab["components"])


class TestBuildViewLayoutMetrics:
    def test_multiple_metric_cards_in_grid(self):
        components = [
            {"kind": "metric_card", "title": "CPU", "value": "72%"},
            {"kind": "metric_card", "title": "Memory", "value": "3.2Gi"},
            {"kind": "metric_card", "title": "Restarts", "value": "5"},
        ]
        result = build_view_layout(components, "incident")
        hero = result[0]
        grid = hero["components"][-1]
        assert grid["kind"] == "grid"
        assert grid["columns"] == 3
        assert len(grid["items"]) == 3

    def test_no_metric_cards_no_grid(self):
        components = [{"kind": "resolution_tracker", "steps": []}]
        result = build_view_layout(components, "incident")
        hero = result[0]
        assert not any(c.get("kind") == "grid" for c in hero["components"])
