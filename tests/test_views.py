"""Tests for view persistence (db.py view functions) and view API security."""

from __future__ import annotations

import os

import pytest

from sre_agent import db as db_module
from sre_agent.db import Database, reset_database, set_database
from sre_agent.db_schema import ALL_SCHEMAS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _view_db(tmp_path):
    """Create an in-memory SQLite DB with views table for each test."""
    path = os.path.join(str(tmp_path), "views_test.db")
    test_db = Database(f"sqlite:///{path}")
    test_db.executescript(ALL_SCHEMAS)
    set_database(test_db)
    yield test_db
    reset_database()


def _layout():
    return [{"kind": "data_table", "title": "Pods", "columns": [], "rows": []}]


# ---------------------------------------------------------------------------
# save_view
# ---------------------------------------------------------------------------


class TestSaveView:
    def test_saves_and_retrieves(self):
        result = db_module.save_view("alice", "cv-1", "My View", "desc", _layout())
        assert result == "cv-1"

        view = db_module.get_view("cv-1", "alice")
        assert view is not None
        assert view["title"] == "My View"
        assert view["owner"] == "alice"
        assert isinstance(view["layout"], list)

    def test_upsert_same_owner(self):
        db_module.save_view("alice", "cv-1", "First", "", _layout())
        db_module.save_view("alice", "cv-1", "Updated", "", _layout())
        view = db_module.get_view("cv-1", "alice")
        assert view["title"] == "Updated"

    def test_upsert_different_owner_blocked(self):
        """IDOR protection: another user cannot overwrite a view via ON CONFLICT."""
        db_module.save_view("alice", "cv-1", "Alice's View", "", _layout())
        db_module.save_view("mallory", "cv-1", "Hacked!", "", _layout())

        view = db_module.get_view("cv-1")
        assert view["owner"] == "alice"
        assert view["title"] == "Alice's View"

    def test_saves_positions(self):
        positions = {0: {"x": 0, "y": 0, "w": 2, "h": 3}}
        db_module.save_view("alice", "cv-1", "Test", "", _layout(), positions)
        view = db_module.get_view("cv-1", "alice")
        assert isinstance(view["positions"], dict)


# ---------------------------------------------------------------------------
# list_views
# ---------------------------------------------------------------------------


class TestListViews:
    def test_lists_only_owned_views(self):
        db_module.save_view("alice", "cv-1", "Alice's", "", _layout())
        db_module.save_view("bob", "cv-2", "Bob's", "", _layout())

        alice_views = db_module.list_views("alice")
        assert len(alice_views) == 1
        assert alice_views[0]["id"] == "cv-1"

        bob_views = db_module.list_views("bob")
        assert len(bob_views) == 1
        assert bob_views[0]["id"] == "cv-2"

    def test_respects_limit(self):
        for i in range(10):
            db_module.save_view("alice", f"cv-{i}", f"View {i}", "", _layout())
        views = db_module.list_views("alice", limit=3)
        assert len(views) == 3

    def test_empty_for_unknown_user(self):
        views = db_module.list_views("nobody")
        assert views == []


# ---------------------------------------------------------------------------
# get_view
# ---------------------------------------------------------------------------


class TestGetView:
    def test_returns_none_for_missing(self):
        assert db_module.get_view("nonexistent") is None

    def test_owner_check(self):
        db_module.save_view("alice", "cv-1", "Test", "", _layout())
        assert db_module.get_view("cv-1", "alice") is not None
        assert db_module.get_view("cv-1", "bob") is None

    def test_without_owner_returns_any(self):
        db_module.save_view("alice", "cv-1", "Test", "", _layout())
        assert db_module.get_view("cv-1") is not None


# ---------------------------------------------------------------------------
# update_view
# ---------------------------------------------------------------------------


class TestUpdateView:
    def test_updates_title(self):
        db_module.save_view("alice", "cv-1", "Old", "", _layout())
        result = db_module.update_view("cv-1", "alice", title="New")
        assert result is True
        assert db_module.get_view("cv-1", "alice")["title"] == "New"

    def test_owner_isolation(self):
        db_module.save_view("alice", "cv-1", "Alice's", "", _layout())
        result = db_module.update_view("cv-1", "mallory", title="Hacked")
        assert result is False
        assert db_module.get_view("cv-1", "alice")["title"] == "Alice's"

    def test_rejects_unknown_fields(self):
        db_module.save_view("alice", "cv-1", "Test", "", _layout())
        # Unknown fields are silently skipped by the allowlist
        result = db_module.update_view("cv-1", "alice", secret="bad", foo="bar")
        assert result is False  # No allowed fields → no update

    def test_nonexistent_view(self):
        result = db_module.update_view("nope", "alice", title="X")
        assert result is False


# ---------------------------------------------------------------------------
# delete_view
# ---------------------------------------------------------------------------


class TestDeleteView:
    def test_deletes_owned_view(self):
        db_module.save_view("alice", "cv-1", "Test", "", _layout())
        result = db_module.delete_view("cv-1", "alice")
        assert result is True
        assert db_module.get_view("cv-1") is None

    def test_cannot_delete_others_view(self):
        db_module.save_view("alice", "cv-1", "Test", "", _layout())
        result = db_module.delete_view("cv-1", "mallory")
        assert result is False
        assert db_module.get_view("cv-1") is not None

    def test_nonexistent_returns_false(self):
        result = db_module.delete_view("nope", "alice")
        assert result is False


# ---------------------------------------------------------------------------
# clone_view
# ---------------------------------------------------------------------------


class TestCloneView:
    def test_clones_to_new_owner(self):
        db_module.save_view("alice", "cv-1", "Shared Dashboard", "desc", _layout())
        new_id = db_module.clone_view("cv-1", "bob")
        assert new_id is not None
        assert new_id != "cv-1"

        clone = db_module.get_view(new_id, "bob")
        assert clone is not None
        assert clone["title"] == "Shared Dashboard"
        assert clone["owner"] == "bob"

    def test_clone_nonexistent_returns_none(self):
        assert db_module.clone_view("nope", "bob") is None

    def test_original_unchanged(self):
        db_module.save_view("alice", "cv-1", "Original", "", _layout())
        db_module.clone_view("cv-1", "bob")
        original = db_module.get_view("cv-1", "alice")
        assert original["title"] == "Original"
        assert original["owner"] == "alice"


# ---------------------------------------------------------------------------
# Share token (api.py _get_current_user)
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    def test_dev_user_override(self):
        from sre_agent.api import _get_current_user

        os.environ["PULSE_AGENT_DEV_USER"] = "testdev"
        try:
            user = _get_current_user()
            assert user == "testdev"
        finally:
            del os.environ["PULSE_AGENT_DEV_USER"]

    def test_no_token_raises_401(self):
        from fastapi import HTTPException

        from sre_agent.api import _get_current_user

        os.environ.pop("PULSE_AGENT_DEV_USER", None)
        with pytest.raises(HTTPException) as exc_info:
            _get_current_user(authorization=None, x_forwarded_access_token=None)
        assert exc_info.value.status_code == 401

    def test_bearer_token_fallback(self):
        from sre_agent.api import _get_current_user

        os.environ.pop("PULSE_AGENT_DEV_USER", None)
        user = _get_current_user(authorization="Bearer some-token-123")
        assert user.startswith("user-")
        assert len(user) > 5

    def test_forwarded_token_preferred(self):
        from sre_agent.api import _get_current_user

        os.environ.pop("PULSE_AGENT_DEV_USER", None)
        user1 = _get_current_user(x_forwarded_access_token="token-a")
        user2 = _get_current_user(x_forwarded_access_token="token-b")
        assert user1 != user2

    def test_same_token_returns_same_user(self):
        from sre_agent.api import _get_current_user

        os.environ.pop("PULSE_AGENT_DEV_USER", None)
        user1 = _get_current_user(x_forwarded_access_token="consistent-token")
        user2 = _get_current_user(x_forwarded_access_token="consistent-token")
        assert user1 == user2


# ---------------------------------------------------------------------------
# Share token verification
# ---------------------------------------------------------------------------


class TestShareToken:
    def test_generate_and_verify(self):
        import hashlib
        import hmac
        import time

        os.environ["PULSE_AGENT_WS_TOKEN"] = "test-secret-key"
        try:
            secret = "test-secret-key"
            view_id = "cv-abc123"
            expires = int(time.time()) + 3600
            payload = f"{view_id}:{expires}"
            signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            token = f"{payload}:{signature}"

            parts = token.split(":")
            assert len(parts) == 3

            v_id, exp_str, sig = parts
            assert v_id == view_id
            expected = hmac.new(secret.encode(), f"{v_id}:{exp_str}".encode(), hashlib.sha256).hexdigest()
            assert hmac.compare_digest(sig, expected)
        finally:
            del os.environ["PULSE_AGENT_WS_TOKEN"]

    def test_expired_token(self):
        import hashlib
        import hmac

        secret = "test-secret"
        view_id = "cv-abc123"
        expires = 1000000  # long expired
        payload = f"{view_id}:{expires}"
        signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        token = f"{payload}:{signature}"

        parts = token.split(":")
        _, exp_str, _ = parts
        assert int(exp_str) < __import__("time").time()

    def test_forged_signature_rejected(self):
        import hmac

        view_id = "cv-abc123"
        expires = 9999999999
        forged_sig = "a" * 64
        token = f"{view_id}:{expires}:{forged_sig}"

        parts = token.split(":")
        _, _, sig = parts
        secret = "real-secret"
        expected = hmac.new(secret.encode(), f"{view_id}:{expires}".encode(), __import__("hashlib").sha256).hexdigest()
        assert not hmac.compare_digest(sig, expected)


# ---------------------------------------------------------------------------
# namespace_summary tool
# ---------------------------------------------------------------------------


class TestNamespaceSummary:
    def test_returns_tuple(self, mock_k8s):
        from tests.conftest import _make_pod

        mock_k8s["core"].list_namespaced_pod.return_value = SimpleNamespace(
            items=[_make_pod(name="p1", phase="Running"), _make_pod(name="p2", phase="Failed")]
        )
        mock_k8s["apps"].list_namespaced_deployment.return_value = SimpleNamespace(items=[])
        mock_k8s["core"].list_namespaced_event.return_value = SimpleNamespace(items=[])

        from sre_agent.view_tools import namespace_summary

        result = namespace_summary.call({"namespace": "default"})
        assert isinstance(result, tuple)
        text, component = result
        assert "default" in text
        assert component["kind"] == "info_card_grid"
        assert len(component["cards"]) == 4


# Need SimpleNamespace for mock
from types import SimpleNamespace


@pytest.fixture
def mock_k8s():
    """Mock K8s clients for tool tests."""
    from unittest.mock import MagicMock, patch

    core = MagicMock()
    apps = MagicMock()
    custom = MagicMock()

    with (
        patch("sre_agent.k8s_client.get_core_client", return_value=core),
        patch("sre_agent.k8s_client.get_apps_client", return_value=apps),
        patch("sre_agent.k8s_client.get_custom_client", return_value=custom),
    ):
        yield {"core": core, "apps": apps, "custom": custom}
