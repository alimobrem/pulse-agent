"""Tests for sre_agent.error_tracker — ring buffer error tracking."""

import threading
import pytest

from sre_agent.errors import ToolError
from sre_agent.error_tracker import ErrorTracker, get_tracker


def _make_error(category: str = "server", operation: str = "test_tool") -> ToolError:
    return ToolError(message="test error", category=category, operation=operation)


class TestErrorTracker:
    def test_record_and_get_recent(self):
        tracker = ErrorTracker(max_entries=10)
        tracker.record(_make_error("permission"))
        tracker.record(_make_error("not_found"))

        recent = tracker.get_recent(limit=10)
        assert len(recent) == 2
        # Most recent first
        assert recent[0]["category"] == "not_found"
        assert recent[1]["category"] == "permission"

    def test_ring_buffer_eviction(self):
        tracker = ErrorTracker(max_entries=3)
        for i in range(5):
            tracker.record(_make_error(f"cat_{i}", f"tool_{i}"))

        recent = tracker.get_recent(limit=10)
        assert len(recent) == 3
        # Oldest (cat_0, cat_1) should be evicted
        categories = [r["category"] for r in recent]
        assert "cat_0" not in categories
        assert "cat_1" not in categories

    def test_get_summary(self):
        tracker = ErrorTracker()
        tracker.record(_make_error("permission", "list_pods"))
        tracker.record(_make_error("permission", "get_pod"))
        tracker.record(_make_error("server", "list_pods"))

        summary = tracker.get_summary()
        assert summary["total"] == 3
        assert summary["by_category"]["permission"] == 2
        assert summary["by_category"]["server"] == 1
        assert "list_pods" in summary["top_tools"]
        assert summary["top_tools"]["list_pods"] == 2

    def test_clear(self):
        tracker = ErrorTracker()
        tracker.record(_make_error())
        tracker.clear()
        assert tracker.get_summary()["total"] == 0
        assert tracker.get_recent() == []

    def test_thread_safety(self):
        tracker = ErrorTracker(max_entries=1000)
        errors = []

        def writer():
            for _ in range(100):
                tracker.record(_make_error())

        threads = [threading.Thread(target=writer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = tracker.get_summary()
        assert summary["total"] == 500

    def test_get_tracker_singleton(self):
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2

    def test_limit_on_get_recent(self):
        tracker = ErrorTracker()
        for i in range(10):
            tracker.record(_make_error())
        recent = tracker.get_recent(limit=3)
        assert len(recent) == 3
