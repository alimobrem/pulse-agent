"""Tests for ACM Thanos recipe compatibility tagging, filtering, and fleet tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sre_agent.prometheus import (
    CHART_COLORS,
    PrometheusBackend,
    PrometheusClient,
    parse_time_range,
)
from sre_agent.promql_recipes import (
    RECIPES,
    PromQLRecipe,
    check_thanos_compatibility,
    get_recipes_for_category,
    inject_cluster_label,
)


class TestACMSafeTagging:
    def test_raw_metrics_default_to_safe(self):
        r = PromQLRecipe("test", "up", "line", "desc", "up", "cluster")
        assert r.acm_safe is True

    def test_explicit_false_overrides_default(self):
        r = PromQLRecipe("test", "up", "line", "desc", "up", "cluster", acm_safe=False)
        assert r.acm_safe is False

    def test_ocp_recording_rules_tagged_unsafe(self):
        for cat, recipes in RECIPES.items():
            for r in recipes:
                if r.metric.startswith(("instance:", "pod:", "namespace:", "workload:", "instance_device:")):
                    assert r.acm_safe is False, f"[{cat}] {r.name} should be acm_safe=False"

    def test_acm_hub_recording_rules_tagged_safe(self):
        hub_metrics = {"cluster:cpu_usage_cores:sum", "cluster:memory_usage_bytes:sum", "cluster:node_cpu:ratio"}
        for cat, recipes in RECIPES.items():
            for r in recipes:
                if r.metric in hub_metrics:
                    assert r.acm_safe is True, f"[{cat}] {r.name} should be acm_safe=True"

    def test_acm_fleet_recipes_all_safe(self):
        fleet = RECIPES.get("acm_fleet", [])
        assert len(fleet) >= 10
        for r in fleet:
            assert r.acm_safe is True, f"Fleet recipe {r.name} should be acm_safe=True"

    def test_total_safe_vs_unsafe_counts(self):
        safe = sum(1 for rr in RECIPES.values() for r in rr if r.acm_safe)
        unsafe = sum(1 for rr in RECIPES.values() for r in rr if not r.acm_safe)
        assert safe >= 60
        assert unsafe >= 15
        assert safe + unsafe == sum(len(v) for v in RECIPES.values())


class TestACMRecipeFiltering:
    def test_acm_only_filter(self):
        all_cpu = get_recipes_for_category("cpu")
        safe_cpu = get_recipes_for_category("cpu", acm_only=True)
        assert len(safe_cpu) < len(all_cpu)
        assert all(r.acm_safe for r in safe_cpu)

    def test_acm_only_on_acm_fleet(self):
        fleet = get_recipes_for_category("acm_fleet", acm_only=True)
        assert len(fleet) >= 10

    def test_acm_only_on_node_use_filters_ocp_rules(self):
        all_node = get_recipes_for_category("node_use")
        safe_node = get_recipes_for_category("node_use", acm_only=True)
        assert len(safe_node) < len(all_node)

    def test_no_filter_returns_all(self):
        all_cpu = get_recipes_for_category("cpu")
        assert any(not r.acm_safe for r in all_cpu)


class TestACMClusterLabelOnFleetRecipes:
    def test_fleet_recipes_injectable(self):
        for r in RECIPES.get("acm_fleet", []):
            q = inject_cluster_label(r.query, "test-cluster")
            assert 'cluster="test-cluster"' in q, f"Failed for {r.name}"

    def test_fleet_recipes_render_with_cluster(self):
        for r in RECIPES.get("acm_fleet", []):
            rendered = r.render(cluster="prod-east")
            assert 'cluster="prod-east"' in rendered, f"render() failed for {r.name}"


class TestThanosCompatOnFleetRecipes:
    def test_fleet_recipes_are_thanos_compatible(self):
        for r in RECIPES.get("acm_fleet", []):
            warning = check_thanos_compatibility(r.query)
            assert warning is None, f"Fleet recipe {r.name} is not Thanos-compatible: {warning}"


class TestParseTimeRange:
    def test_minutes(self):
        assert parse_time_range("5m") == 300

    def test_hours(self):
        assert parse_time_range("1h") == 3600

    def test_days(self):
        assert parse_time_range("7d") == 604800

    def test_seconds(self):
        assert parse_time_range("30s") == 30

    def test_invalid_returns_default(self):
        assert parse_time_range("bad") == 3600

    def test_empty_returns_default(self):
        assert parse_time_range("") == 3600


class TestChartColors:
    def test_has_8_colors(self):
        assert len(CHART_COLORS) == 8

    def test_all_hex(self):
        for c in CHART_COLORS:
            assert c.startswith("#")
            assert len(c) == 7


class TestPrometheusClientDualBackendE2E:
    def test_query_routes_to_local_by_default(self):
        client = PrometheusClient()
        with patch.object(client, "request") as mock_req:
            mock_req.return_value = {"status": "success", "data": {"result": []}}
            client.query("up")
            mock_req.assert_called_once()
            assert mock_req.call_args[0][3] == PrometheusBackend.LOCAL

    def test_query_routes_to_acm_when_specified(self):
        client = PrometheusClient()
        with patch.object(client, "request") as mock_req:
            mock_req.return_value = {"status": "success", "data": {"result": []}}
            client.query("up", backend=PrometheusBackend.ACM)
            assert mock_req.call_args[0][3] == PrometheusBackend.ACM

    def test_query_range_routes_to_acm(self):
        client = PrometheusClient()
        with patch.object(client, "request") as mock_req:
            mock_req.return_value = {"status": "success", "data": {"result": []}}
            client.query_range("up", 1000, 2000, 60, backend=PrometheusBackend.ACM)
            assert mock_req.call_args[0][3] == PrometheusBackend.ACM

    def test_acm_detection_gates_fleet_tools(self):
        mock_client = MagicMock()
        mock_client.is_acm_available.return_value = False
        with patch("sre_agent.prometheus.get_prometheus_client", return_value=mock_client):
            from sre_agent.fleet_tools import fleet_query_metrics

            result = fleet_query_metrics("up")
            assert "not available" in result.lower()

    def test_acm_available_allows_fleet_tools(self):
        mock_client = MagicMock()
        mock_client.is_acm_available.return_value = True
        mock_client.query_range.return_value = {
            "status": "success",
            "data": {"result": [{"metric": {"cluster": "prod"}, "values": [[1000, "42"]]}]},
        }
        with (
            patch("sre_agent.prometheus.get_prometheus_client", return_value=mock_client),
            patch("sre_agent.promql_recipes.check_thanos_compatibility", return_value=None),
        ):
            from sre_agent.fleet_tools import fleet_query_metrics

            result = fleet_query_metrics("up")
            assert isinstance(result, tuple)
            text, component = result
            assert "prod" in text
            assert component["kind"] == "chart"
