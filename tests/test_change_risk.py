"""Tests for change risk scoring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sre_agent.change_risk import score_deployment_change


class TestChangeRiskScoring:
    def test_low_risk_tag_change(self):
        result = score_deployment_change(
            deployment_name="web",
            namespace="prod",
            old_image="app:v1.0",
            new_image="app:v1.1",
        )
        assert result.level in ("LOW", "MEDIUM")
        assert result.score < 50

    def test_high_risk_new_image(self):
        result = score_deployment_change(
            deployment_name="web",
            namespace="prod",
            old_image="app:v1.0",
            new_image="completely-different:latest",
            resource_changes=True,
            config_changes=True,
        )
        assert result.score > 30
        assert len(result.factors) >= 2

    def test_no_change(self):
        result = score_deployment_change(
            deployment_name="web",
            namespace="prod",
        )
        assert result.level == "LOW" or result.score < 25

    def test_returns_recommendation(self):
        result = score_deployment_change(
            deployment_name="web",
            namespace="prod",
            old_image="a:1",
            new_image="b:2",
        )
        assert result.recommendation != ""

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_blast_radius_increases_score(self, mock_graph_fn):
        graph = MagicMock()
        graph.downstream_blast_radius.return_value = ["Pod/default/p" + str(i) for i in range(15)]
        mock_graph_fn.return_value = graph

        result = score_deployment_change(
            deployment_name="web",
            namespace="prod",
            old_image="a:1",
            new_image="a:2",
        )
        assert any("blast radius" in f.lower() for f in result.factors)
