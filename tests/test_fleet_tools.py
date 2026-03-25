"""Tests for fleet-wide tools."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_k8s_config():
    with patch("sre_agent.k8s_client.config"):
        with patch("sre_agent.k8s_client._initialized", True):
            yield


def _mock_managed_clusters():
    return [
        {"name": "prod-east", "available": True},
        {"name": "prod-west", "available": True},
        {"name": "staging", "available": False},
    ]


class TestFleetListClusters:
    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=_mock_managed_clusters())
    def test_lists_clusters(self, mock_clusters):
        from sre_agent.fleet_tools import fleet_list_clusters
        result = fleet_list_clusters()
        text, component = result
        assert "prod-east" in text
        assert "prod-west" in text
        assert "3 managed clusters" in text
        assert component["kind"] == "status_list"
        assert len(component["items"]) == 3

    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=[])
    def test_no_clusters(self, mock_clusters):
        from sre_agent.fleet_tools import fleet_list_clusters
        result = fleet_list_clusters()
        assert "No managed clusters" in result


class TestFleetListPods:
    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=[])
    def test_no_clusters(self, mock_clusters):
        from sre_agent.fleet_tools import fleet_list_pods
        result = fleet_list_pods()
        assert "No managed clusters" in result

    @patch("sre_agent.fleet_tools._proxy_core_client")
    @patch("sre_agent.fleet_tools.get_core_client")
    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=[{"name": "prod", "available": True}])
    def test_aggregates_pods(self, mock_clusters, mock_core, mock_proxy):
        from sre_agent.fleet_tools import fleet_list_pods

        # Mock local cluster
        mock_pod = MagicMock()
        mock_pod.metadata.namespace = "default"
        mock_pod.metadata.name = "local-pod"
        mock_pod.metadata.creation_timestamp = None
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = []
        mock_pod.spec.node_name = "node-1"

        mock_result = MagicMock()
        mock_result.items = [mock_pod]
        mock_core.return_value.list_namespaced_pod.return_value = mock_result

        # Mock remote cluster
        mock_remote_pod = MagicMock()
        mock_remote_pod.metadata.namespace = "default"
        mock_remote_pod.metadata.name = "remote-pod"
        mock_remote_pod.metadata.creation_timestamp = None
        mock_remote_pod.status.phase = "Running"
        mock_remote_pod.status.container_statuses = []
        mock_remote_pod.spec.node_name = "node-2"

        mock_remote_result = MagicMock()
        mock_remote_result.items = [mock_remote_pod]
        mock_proxy.return_value.list_namespaced_pod.return_value = mock_remote_result

        result = fleet_list_pods(namespace="default")
        text, component = result
        assert "local: 1 pods" in text
        assert "prod: 1 pods" in text
        assert "Total: 2 pods" in text
        assert component["kind"] == "data_table"
        assert len(component["rows"]) == 2


class TestFleetCompareResource:
    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=[])
    def test_no_clusters(self, mock_clusters):
        from sre_agent.fleet_tools import fleet_compare_resource
        result = fleet_compare_resource(kind="Deployment", name="web", namespace="default")
        assert "No managed clusters" in result

    @patch("sre_agent.fleet_tools._proxy_apps_client")
    @patch("sre_agent.fleet_tools.get_apps_client")
    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=[{"name": "prod", "available": True}])
    def test_detects_drift(self, mock_clusters, mock_apps, mock_proxy):
        from sre_agent.fleet_tools import fleet_compare_resource

        local_dep = MagicMock()
        local_dep.to_dict.return_value = {
            "metadata": {"name": "web"},
            "spec": {"replicas": 3, "template": {"spec": {"containers": [{"name": "web", "image": "nginx:1.0"}]}}},
        }
        mock_apps.return_value.read_namespaced_deployment.return_value = local_dep

        remote_dep = MagicMock()
        remote_dep.to_dict.return_value = {
            "metadata": {"name": "web"},
            "spec": {"replicas": 5, "template": {"spec": {"containers": [{"name": "web", "image": "nginx:2.0"}]}}},
        }
        mock_proxy.return_value.read_namespaced_deployment.return_value = remote_dep

        result = fleet_compare_resource(kind="Deployment", name="web", namespace="default")
        text, component = result
        assert "Drift detected" in text
        assert "spec.replicas" in text
        assert component["kind"] == "data_table"

    @patch("sre_agent.fleet_tools._proxy_apps_client")
    @patch("sre_agent.fleet_tools.get_apps_client")
    @patch("sre_agent.fleet_tools._get_managed_clusters", return_value=[{"name": "prod", "available": True}])
    def test_no_drift(self, mock_clusters, mock_apps, mock_proxy):
        from sre_agent.fleet_tools import fleet_compare_resource

        dep_dict = {
            "metadata": {"name": "web"},
            "spec": {"replicas": 3, "template": {"spec": {"containers": [{"name": "web", "image": "nginx:1.0"}]}}},
        }

        local_dep = MagicMock()
        local_dep.to_dict.return_value = dep_dict
        mock_apps.return_value.read_namespaced_deployment.return_value = local_dep

        remote_dep = MagicMock()
        remote_dep.to_dict.return_value = dep_dict
        mock_proxy.return_value.read_namespaced_deployment.return_value = remote_dep

        result = fleet_compare_resource(kind="Deployment", name="web", namespace="default")
        assert "identical" in result
        assert "No drift" in result
