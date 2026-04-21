"""Tests for view lifecycle — status transitions and claim mechanism."""

from __future__ import annotations

import pytest

from sre_agent import db as db_module
from sre_agent.db import Database, reset_database, set_database
from sre_agent.db_schema import ALL_SCHEMAS


@pytest.fixture(autouse=True)
def _view_db():
    from tests.conftest import _TEST_DB_URL

    test_db = Database(_TEST_DB_URL)
    test_db.execute("DROP TABLE IF EXISTS view_versions CASCADE")
    test_db.execute("DROP TABLE IF EXISTS views CASCADE")
    test_db.commit()
    test_db.executescript(ALL_SCHEMAS)
    set_database(test_db)
    yield test_db
    reset_database()


def _layout():
    return [{"kind": "data_table", "title": "Pods", "columns": [], "rows": []}]


def _create_incident():
    db_module.save_view(
        "alice",
        "cv-inc-1",
        "CrashLoop",
        "desc",
        _layout(),
        view_type="incident",
        status="investigating",
        visibility="team",
        trigger_source="monitor",
        finding_id="f-crash-1",
    )
    return "cv-inc-1"


class TestStatusTransition:
    def test_valid_incident_transition(self):
        view_id = _create_incident()
        ok = db_module.transition_view_status(view_id, "alice", "action_taken")
        assert ok is True
        view = db_module.get_view(view_id)
        assert view["status"] == "action_taken"

    def test_invalid_transition_rejected(self):
        view_id = _create_incident()
        ok = db_module.transition_view_status(view_id, "alice", "completed")
        assert ok is False
        view = db_module.get_view(view_id)
        assert view["status"] == "investigating"

    def test_custom_views_cannot_transition(self):
        db_module.save_view("alice", "cv-custom", "Custom", "", _layout())
        ok = db_module.transition_view_status("cv-custom", "alice", "resolved")
        assert ok is False

    def test_transition_creates_version(self):
        view_id = _create_incident()
        db_module.transition_view_status(view_id, "alice", "action_taken")
        versions = db_module.list_view_versions(view_id)
        actions = [v["action"] for v in versions]
        assert any("action_taken" in a for a in actions)

    def test_full_incident_lifecycle(self):
        view_id = _create_incident()
        assert db_module.transition_view_status(view_id, "alice", "action_taken")
        assert db_module.transition_view_status(view_id, "alice", "verifying")
        assert db_module.transition_view_status(view_id, "alice", "resolved")
        assert db_module.transition_view_status(view_id, "alice", "archived")
        view = db_module.get_view(view_id)
        assert view["status"] == "archived"

    def test_plan_lifecycle(self):
        db_module.save_view(
            "alice",
            "cv-plan",
            "Plan",
            "",
            _layout(),
            view_type="plan",
            status="analyzing",
            visibility="team",
        )
        assert db_module.transition_view_status("cv-plan", "alice", "ready")
        assert db_module.transition_view_status("cv-plan", "alice", "executing")
        assert db_module.transition_view_status("cv-plan", "alice", "completed")
        view = db_module.get_view("cv-plan")
        assert view["status"] == "completed"

    def test_assessment_lifecycle(self):
        db_module.save_view(
            "alice",
            "cv-assess",
            "Assessment",
            "",
            _layout(),
            view_type="assessment",
            status="analyzing",
            visibility="team",
        )
        assert db_module.transition_view_status("cv-assess", "alice", "ready")
        assert db_module.transition_view_status("cv-assess", "alice", "acknowledged")
        view = db_module.get_view("cv-assess")
        assert view["status"] == "acknowledged"

    def test_nonexistent_view(self):
        ok = db_module.transition_view_status("nonexistent", "alice", "action_taken")
        assert ok is False


class TestClaimView:
    def test_claim_view(self):
        view_id = _create_incident()
        ok = db_module.claim_view(view_id, "bob")
        assert ok is True
        view = db_module.get_view(view_id)
        assert view["claimed_by"] == "bob"
        assert view["claimed_at"] is not None

    def test_unclaim_view(self):
        view_id = _create_incident()
        db_module.claim_view(view_id, "bob")
        ok = db_module.unclaim_view(view_id, "bob")
        assert ok is True
        view = db_module.get_view(view_id)
        assert view["claimed_by"] is None

    def test_claim_private_view_denied(self):
        db_module.save_view("alice", "cv-priv", "Private", "", _layout())
        ok = db_module.claim_view("cv-priv", "bob")
        assert ok is False

    def test_unclaim_wrong_user_denied(self):
        view_id = _create_incident()
        db_module.claim_view(view_id, "bob")
        ok = db_module.unclaim_view(view_id, "charlie")
        assert ok is False
        view = db_module.get_view(view_id)
        assert view["claimed_by"] == "bob"


class TestFindByFinding:
    def test_find_view_by_finding_id(self):
        _create_incident()
        view = db_module.get_view_by_finding("f-crash-1")
        assert view is not None
        assert view["id"] == "cv-inc-1"

    def test_find_returns_none_for_unknown(self):
        view = db_module.get_view_by_finding("nonexistent")
        assert view is None
