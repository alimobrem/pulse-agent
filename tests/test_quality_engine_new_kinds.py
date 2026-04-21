"""Tests for Phase 2 component validation rules."""

from __future__ import annotations

from sre_agent.quality_engine import QualityResult, _validate_component


def _validate(comp: dict) -> QualityResult:
    result = QualityResult()
    _validate_component(comp, result)
    return result


class TestConfidenceBadgeValidation:
    def test_valid(self):
        r = _validate({"kind": "confidence_badge", "score": 0.85})
        assert not r.errors

    def test_missing_score(self):
        r = _validate({"kind": "confidence_badge"})
        assert any("score" in e for e in r.errors)

    def test_score_out_of_range_high(self):
        r = _validate({"kind": "confidence_badge", "score": 1.5})
        assert any("0.0 and 1.0" in e for e in r.errors)

    def test_score_out_of_range_negative(self):
        r = _validate({"kind": "confidence_badge", "score": -0.1})
        assert any("0.0 and 1.0" in e for e in r.errors)

    def test_score_zero_valid(self):
        r = _validate({"kind": "confidence_badge", "score": 0.0})
        assert not r.errors

    def test_score_one_valid(self):
        r = _validate({"kind": "confidence_badge", "score": 1.0})
        assert not r.errors

    def test_no_title_required(self):
        r = _validate({"kind": "confidence_badge", "score": 0.5})
        assert not any("title" in e for e in r.errors)


class TestResolutionTrackerValidation:
    def test_valid(self):
        r = _validate(
            {
                "kind": "resolution_tracker",
                "steps": [{"title": "Step 1", "status": "done", "detail": "Complete"}],
            }
        )
        assert not r.errors

    def test_empty_steps(self):
        r = _validate({"kind": "resolution_tracker", "steps": []})
        assert any("at least 1 step" in e for e in r.errors)

    def test_missing_steps(self):
        r = _validate({"kind": "resolution_tracker"})
        assert any("at least 1 step" in e for e in r.errors)

    def test_step_missing_title(self):
        r = _validate(
            {
                "kind": "resolution_tracker",
                "steps": [{"status": "done", "detail": "no title"}],
            }
        )
        assert any("step missing 'title'" in e for e in r.errors)

    def test_step_invalid_status(self):
        r = _validate(
            {
                "kind": "resolution_tracker",
                "steps": [{"title": "Step 1", "status": "invalid_status"}],
            }
        )
        assert any("status must be one of" in e for e in r.errors)

    def test_all_valid_statuses(self):
        for status in ("done", "running", "pending"):
            r = _validate(
                {
                    "kind": "resolution_tracker",
                    "steps": [{"title": "Step", "status": status, "detail": "x"}],
                }
            )
            assert not r.errors, f"Status '{status}' should be valid"


class TestBlastRadiusValidation:
    def test_valid(self):
        r = _validate(
            {
                "kind": "blast_radius",
                "title": "Blast Radius — payment-api",
                "items": [
                    {
                        "kind_abbrev": "Svc",
                        "name": "payment-api",
                        "relationship": "selects",
                        "status": "degraded",
                        "status_detail": "0 endpoints",
                    }
                ],
            }
        )
        assert not r.errors

    def test_empty_items(self):
        r = _validate({"kind": "blast_radius", "title": "Blast Radius", "items": []})
        assert any("at least 1 item" in e for e in r.errors)

    def test_missing_items(self):
        r = _validate({"kind": "blast_radius", "title": "Blast Radius"})
        assert any("at least 1 item" in e for e in r.errors)

    def test_item_missing_kind_abbrev(self):
        r = _validate(
            {
                "kind": "blast_radius",
                "title": "Blast Radius",
                "items": [{"name": "svc", "relationship": "selects", "status": "healthy"}],
            }
        )
        assert any("kind_abbrev" in e for e in r.errors)

    def test_item_missing_name(self):
        r = _validate(
            {
                "kind": "blast_radius",
                "title": "Blast Radius",
                "items": [{"kind_abbrev": "Svc", "relationship": "selects", "status": "healthy"}],
            }
        )
        assert any("'name'" in e for e in r.errors)

    def test_item_invalid_status(self):
        r = _validate(
            {
                "kind": "blast_radius",
                "title": "Blast Radius",
                "items": [{"kind_abbrev": "Svc", "name": "x", "relationship": "selects", "status": "unknown_status"}],
            }
        )
        assert any("status must be one of" in e for e in r.errors)


class TestActionButtonValidation:
    def test_valid(self):
        r = _validate(
            {
                "kind": "action_button",
                "label": "Restart",
                "action": "restart_deployment",
                "action_input": {"name": "nginx", "namespace": "default"},
            }
        )
        assert not r.errors

    def test_missing_label(self):
        r = _validate(
            {
                "kind": "action_button",
                "action": "restart_deployment",
                "action_input": {},
            }
        )
        assert any("label" in e for e in r.errors)

    def test_missing_action(self):
        r = _validate(
            {
                "kind": "action_button",
                "label": "Go",
                "action_input": {},
            }
        )
        assert any("action" in e for e in r.errors)

    def test_missing_action_input(self):
        r = _validate(
            {
                "kind": "action_button",
                "label": "Go",
                "action": "restart_deployment",
            }
        )
        assert any("action_input" in e for e in r.errors)

    def test_action_input_wrong_type(self):
        r = _validate(
            {
                "kind": "action_button",
                "label": "Go",
                "action": "restart_deployment",
                "action_input": "not a dict",
            }
        )
        assert any("action_input" in e for e in r.errors)

    def test_invalid_style(self):
        r = _validate(
            {
                "kind": "action_button",
                "label": "Go",
                "action": "restart_deployment",
                "action_input": {},
                "style": "neon",
            }
        )
        assert any("style" in e for e in r.errors)

    def test_valid_styles(self):
        for style in ("primary", "danger", "ghost"):
            r = _validate(
                {
                    "kind": "action_button",
                    "label": "Go",
                    "action": "x",
                    "action_input": {},
                    "style": style,
                }
            )
            assert not any("style" in e for e in r.errors)
