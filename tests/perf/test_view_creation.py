"""Performance tests — view creation and layout latency.

create_dashboard() signal emission + layout computation must complete in < 1s.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from sre_agent.layout_engine import build_view_layout, compute_layout
from sre_agent.quality_engine import evaluate_components

CREATION_THRESHOLD_S = 1.0


class TestViewCreationLatency:
    def test_create_dashboard_within_threshold(self):
        with (
            patch("sre_agent.k8s_client._initialized", True),
            patch("sre_agent.k8s_client._load_k8s"),
            patch("sre_agent.k8s_client.get_core_client", return_value=MagicMock()),
        ):
            from sre_agent.view_tools import create_dashboard

            start = time.monotonic()
            result = create_dashboard(
                title="Perf Test View",
                description="Testing creation latency",
            )
            elapsed = time.monotonic() - start

            assert elapsed < CREATION_THRESHOLD_S, (
                f"create_dashboard took {elapsed:.2f}s (threshold: {CREATION_THRESHOLD_S}s)"
            )
            text = result[0] if isinstance(result, tuple) else result
            assert "Perf Test View" in text

    def test_create_investigation_view_within_threshold(self):
        with (
            patch("sre_agent.k8s_client._initialized", True),
            patch("sre_agent.k8s_client._load_k8s"),
            patch("sre_agent.k8s_client.get_core_client", return_value=MagicMock()),
        ):
            from sre_agent.view_tools import create_dashboard

            start = time.monotonic()
            create_dashboard(
                title="OOM Investigation",
                description="Pod crashlooping in production",
                view_type="incident",
                trigger_source="monitor",
                finding_id="f-oom-123",
            )
            elapsed = time.monotonic() - start

            assert elapsed < CREATION_THRESHOLD_S, (
                f"Investigation view took {elapsed:.2f}s (threshold: {CREATION_THRESHOLD_S}s)"
            )

    def test_layout_computation_within_threshold(self):
        """compute_layout on a 50-widget view should be fast."""
        layout = [{"kind": "metric_card", "title": f"Metric {i}", "value": f"{i}%"} for i in range(50)]

        start = time.monotonic()
        positions = compute_layout(layout)
        elapsed = time.monotonic() - start

        assert elapsed < CREATION_THRESHOLD_S, (
            f"50-widget layout took {elapsed:.2f}s (threshold: {CREATION_THRESHOLD_S}s)"
        )
        assert len(positions) == 50

    def test_build_view_layout_within_threshold(self):
        """build_view_layout for an incident with many components."""
        components = (
            [{"kind": "confidence_badge", "score": 0.85}]
            + [{"kind": "metric_card", "title": f"M{i}", "value": f"{i}"} for i in range(6)]
            + [
                {
                    "kind": "resolution_tracker",
                    "steps": [{"title": f"Step {j}", "status": "done", "detail": "ok"} for j in range(10)],
                },
                {
                    "kind": "blast_radius",
                    "items": [
                        {
                            "kind_abbrev": "Svc",
                            "name": f"svc-{j}",
                            "relationship": "targets",
                            "status": "degraded",
                            "status_detail": "down",
                        }
                        for j in range(5)
                    ],
                },
                {"kind": "timeline", "lanes": []},
                {"kind": "key_value", "pairs": [{"key": "Root Cause", "value": "OOM"}]},
                {"kind": "data_table", "columns": [{"id": "pod", "header": "Pod"}], "rows": []},
            ]
        )

        start = time.monotonic()
        result = build_view_layout(components, "incident", "investigating")
        elapsed = time.monotonic() - start

        assert elapsed < CREATION_THRESHOLD_S
        assert len(result) == 2
        assert result[0]["kind"] == "section"
        assert result[1]["kind"] == "tabs"

    def test_evaluate_components_within_threshold(self):
        """Quality validation on a large layout should be fast."""
        titles = [
            "CPU Usage",
            "Memory Usage",
            "Disk I/O",
            "Network Throughput",
            "Pod Restarts",
            "API Latency",
            "Error Rate",
            "Request Count",
            "Node Load",
            "Container Count",
        ]
        layout = [{"kind": "metric_card", "title": titles[i % len(titles)], "value": f"{i}%"} for i in range(50)]

        start = time.monotonic()
        evaluate_components(layout)
        elapsed = time.monotonic() - start

        assert elapsed < CREATION_THRESHOLD_S
