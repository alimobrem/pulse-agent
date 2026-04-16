"""Tests for get_topology_graph tool and create_live_table tool."""

from __future__ import annotations

import json
from unittest.mock import patch

from sre_agent.dependency_graph import DependencyGraph


class TestGetTopologyGraph:
    """Tests for the get_topology_graph view tool."""

    def _make_graph(self) -> DependencyGraph:
        g = DependencyGraph()
        g.add_node("Deployment", "production", "web")
        g.add_node("Pod", "production", "web-1")
        g.add_node("Service", "production", "web-svc")
        g.add_edge("Deployment/production/web", "Pod/production/web-1", "owns")
        g.add_edge("Service/production/web-svc", "Pod/production/web-1", "selects")
        return g

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_returns_topology_component(self, mock_get_graph):
        from sre_agent.view_tools import get_topology_graph

        mock_get_graph.return_value = self._make_graph()
        result = get_topology_graph(namespace="production")
        assert isinstance(result, tuple)
        text, component = result
        assert component["kind"] == "topology"
        assert len(component["nodes"]) == 3
        assert len(component["edges"]) == 2
        assert "3 resources" in text

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_filters_by_namespace(self, mock_get_graph):
        from sre_agent.view_tools import get_topology_graph

        g = self._make_graph()
        g.add_node("Pod", "staging", "other-pod")
        mock_get_graph.return_value = g
        result = get_topology_graph(namespace="production")
        _, component = result
        assert len(component["nodes"]) == 3  # staging pod excluded

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_empty_graph_returns_string(self, mock_get_graph):
        from sre_agent.view_tools import get_topology_graph

        mock_get_graph.return_value = DependencyGraph()
        result = get_topology_graph(namespace="production")
        assert isinstance(result, str)
        assert "No topology data" in result

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_all_namespaces(self, mock_get_graph):
        from sre_agent.view_tools import get_topology_graph

        g = self._make_graph()
        g.add_node("Pod", "staging", "other-pod")
        mock_get_graph.return_value = g
        result = get_topology_graph(namespace="")
        _, component = result
        assert len(component["nodes"]) == 4  # all namespaces

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_node_structure(self, mock_get_graph):
        from sre_agent.view_tools import get_topology_graph

        mock_get_graph.return_value = self._make_graph()
        _, component = get_topology_graph(namespace="production")
        node = next(n for n in component["nodes"] if n["kind"] == "Pod")
        assert node["name"] == "web-1"
        assert node["namespace"] == "production"
        assert node["status"] == "healthy"

    @patch("sre_agent.dependency_graph.get_dependency_graph")
    def test_edge_structure(self, mock_get_graph):
        from sre_agent.view_tools import get_topology_graph

        mock_get_graph.return_value = self._make_graph()
        _, component = get_topology_graph(namespace="production")
        owns_edge = next(e for e in component["edges"] if e["relationship"] == "owns")
        assert "Deployment" in owns_edge["source"]
        assert "Pod" in owns_edge["target"]


class TestCreateLiveTable:
    """Tests for the create_live_table tool."""

    def test_valid_k8s_only(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [
            {"type": "k8s", "id": "prod", "label": "Production", "resource": "pods", "namespace": "production"},
            {"type": "k8s", "id": "staging", "label": "Staging", "resource": "pods", "namespace": "staging"},
        ]
        with patch("sre_agent.k8s_tools.live_table._fetch_table_rows") as mock_fetch:
            mock_fetch.return_value = {
                "columns": [{"id": "name", "header": "Name", "type": "resource_name"}],
                "rows": [{"name": "web-1", "_gvr": "v1~pods"}],
                "gvr": "v1~pods",
            }
            result = create_live_table(title="Cross-NS Pods", datasources_json=json.dumps(ds))

        text, component = result
        assert component["kind"] == "data_table"
        assert len(component["datasources"]) == 2
        assert component["rows"]  # initial snapshot
        assert "Live table" in text

    def test_valid_k8s_plus_promql(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [
            {"type": "k8s", "id": "pods", "label": "Pods", "resource": "pods", "namespace": "default"},
            {
                "type": "promql",
                "id": "cpu",
                "label": "CPU",
                "query": "rate(cpu[5m])",
                "columnId": "cpu_usage",
                "columnHeader": "CPU",
                "joinLabel": "pod",
                "joinColumn": "name",
            },
        ]
        with patch("sre_agent.k8s_tools.live_table._fetch_table_rows") as mock_fetch:
            mock_fetch.return_value = {
                "columns": [{"id": "name", "header": "Name", "type": "resource_name"}],
                "rows": [{"name": "web-1"}],
                "gvr": "v1~pods",
            }
            result = create_live_table(title="Pods + CPU", datasources_json=json.dumps(ds))

        _, component = result
        assert len(component["datasources"]) == 2
        # Enrichment column placeholder added
        col_ids = [c["id"] for c in component["columns"]]
        assert "cpu_usage" in col_ids

    def test_invalid_json(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        result = create_live_table(title="Bad", datasources_json="not json")
        assert isinstance(result, str)
        assert "Invalid JSON" in result

    def test_empty_datasources(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        result = create_live_table(title="Bad", datasources_json="[]")
        assert isinstance(result, str)
        assert "non-empty" in result

    def test_too_many_datasources(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [{"type": "k8s", "id": f"ds{i}", "resource": "pods"} for i in range(11)]
        result = create_live_table(title="Bad", datasources_json=json.dumps(ds))
        assert isinstance(result, str)
        assert "Maximum 10" in result

    def test_no_k8s_datasource(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [
            {
                "type": "promql",
                "id": "cpu",
                "query": "rate(cpu[5m])",
                "columnId": "cpu",
                "joinLabel": "pod",
                "joinColumn": "name",
            }
        ]
        result = create_live_table(title="Bad", datasources_json=json.dumps(ds))
        assert isinstance(result, str)
        assert "K8s datasource" in result

    def test_missing_resource(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [{"type": "k8s", "id": "bad", "label": "Bad"}]
        result = create_live_table(title="Bad", datasources_json=json.dumps(ds))
        assert isinstance(result, str)
        assert "missing required 'resource'" in result

    def test_too_many_k8s_datasources(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [{"type": "k8s", "id": f"ds{i}", "label": f"DS{i}", "resource": "pods"} for i in range(6)]
        result = create_live_table(title="Bad", datasources_json=json.dumps(ds))
        assert isinstance(result, str)
        assert "Maximum 5" in result

    def test_promql_missing_join(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [
            {"type": "k8s", "id": "pods", "resource": "pods"},
            {"type": "promql", "id": "cpu", "query": "rate(cpu[5m])", "columnId": "cpu"},
        ]
        result = create_live_table(title="Bad", datasources_json=json.dumps(ds))
        assert isinstance(result, str)
        assert "joinLabel" in result

    def test_logs_missing_namespace(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [
            {"type": "k8s", "id": "pods", "resource": "pods"},
            {"type": "logs", "id": "errs", "columnId": "errors"},
        ]
        result = create_live_table(title="Bad", datasources_json=json.dumps(ds))
        assert isinstance(result, str)
        assert "missing required 'namespace'" in result

    def test_fetch_error_still_returns_spec(self):
        from sre_agent.k8s_tools.live_table import create_live_table

        ds = [{"type": "k8s", "id": "pods", "label": "Pods", "resource": "pods"}]
        with patch("sre_agent.k8s_tools.live_table._fetch_table_rows") as mock_fetch:
            mock_fetch.return_value = "Error: Not running in-cluster (no service account token)."
            result = create_live_table(title="Offline", datasources_json=json.dumps(ds))

        _text, component = result
        assert component["kind"] == "data_table"
        assert component["datasources"]  # spec still present for frontend
        assert component["rows"] == []  # no initial data
