"""Tests for GET /agent/activity endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestBuildActivityEvents:
    def test_returns_events_list(self):
        from sre_agent.api.monitor_rest import _build_activity_events

        mock_db = MagicMock()
        mock_db.fetchall.side_effect = [
            # actions query
            [
                {"category": "crashloop", "namespace": "production", "cnt": 2, "status": "completed"},
                {"category": "workloads", "namespace": "default", "cnt": 1, "status": "completed"},
            ],
            # self-healed findings query
            [{"cnt": 3}],
            # postmortems query
            [{"cnt": 1, "latest_summary": "OOM incident in production"}],
            # investigations query
            [{"finding_type": "node_pressure", "target": "worker-3", "cnt": 1}],
        ]

        events = _build_activity_events(mock_db, days=7)
        assert len(events) >= 2
        assert events[0]["type"] == "auto_fix"
        assert events[0]["count"] == 2
        assert events[0]["namespace"] == "production"
        assert events[0]["link"] == "/incidents?tab=actions"

    def test_empty_when_no_data(self):
        from sre_agent.api.monitor_rest import _build_activity_events

        mock_db = MagicMock()
        mock_db.fetchall.side_effect = [[], [{"cnt": 0}], [], []]

        events = _build_activity_events(mock_db, days=7)
        assert events == []

    def test_no_crash_on_db_error(self):
        from sre_agent.api.monitor_rest import _build_activity_events

        mock_db = MagicMock()
        mock_db.fetchall.side_effect = Exception("DB down")

        events = _build_activity_events(mock_db, days=7)
        assert events == []

    def test_self_healed_included(self):
        from sre_agent.api.monitor_rest import _build_activity_events

        mock_db = MagicMock()
        mock_db.fetchall.side_effect = [
            [],  # no actions
            [{"cnt": 5}],  # 5 self-healed
            [],  # no postmortems
            [],  # no investigations
        ]

        events = _build_activity_events(mock_db, days=7)
        assert len(events) == 1
        assert events[0]["type"] == "self_healed"
        assert events[0]["count"] == 5
        assert "5 findings" in events[0]["description"]

    def test_postmortem_with_summary(self):
        from sre_agent.api.monitor_rest import _build_activity_events

        mock_db = MagicMock()
        mock_db.fetchall.side_effect = [
            [],  # no actions
            [{"cnt": 0}],  # no self-healed
            [{"cnt": 2, "latest_summary": "Memory leak in auth service"}],
            [],  # no investigations
        ]

        events = _build_activity_events(mock_db, days=7)
        assert len(events) == 1
        assert events[0]["type"] == "postmortem"
        assert "Memory leak" in events[0]["description"]
