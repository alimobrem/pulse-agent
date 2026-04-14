"""Tests for K8s resource dependency graph."""

from __future__ import annotations

from sre_agent.dependency_graph import DependencyGraph


class TestDependencyGraph:
    def test_add_node(self):
        g = DependencyGraph()
        key = g.add_node("Pod", "default", "my-pod", {"app": "web"})
        assert key == "Pod/default/my-pod"
        assert g.node_count == 1

    def test_add_edge(self):
        g = DependencyGraph()
        g.add_node("Deployment", "default", "web")
        g.add_node("Pod", "default", "web-abc")
        g.add_edge("Deployment/default/web", "Pod/default/web-abc", "owns")
        assert g.edge_count == 1

    def test_downstream_blast_radius(self):
        g = DependencyGraph()
        g.add_node("Deployment", "default", "web")
        g.add_node("Pod", "default", "web-1")
        g.add_node("Pod", "default", "web-2")
        g.add_edge("Deployment/default/web", "Pod/default/web-1", "owns")
        g.add_edge("Deployment/default/web", "Pod/default/web-2", "owns")
        blast = g.downstream_blast_radius("Deployment", "default", "web")
        assert len(blast) == 2

    def test_upstream_dependencies(self):
        g = DependencyGraph()
        g.add_node("Deployment", "default", "web")
        g.add_node("Pod", "default", "web-1")
        g.add_edge("Deployment/default/web", "Pod/default/web-1", "owns")
        deps = g.upstream_dependencies("Pod", "default", "web-1")
        assert "Deployment/default/web" in deps

    def test_related_resources(self):
        g = DependencyGraph()
        g.add_node("Service", "default", "web-svc")
        g.add_node("Pod", "default", "web-1")
        g.add_node("ConfigMap", "default", "web-config")
        g.add_edge("Service/default/web-svc", "Pod/default/web-1", "selects")
        g.add_edge("Pod/default/web-1", "ConfigMap/default/web-config", "references")
        related = g.related_resources("Pod", "default", "web-1")
        assert len(related) >= 2

    def test_transitive_blast_radius(self):
        g = DependencyGraph()
        g.add_node("Deployment", "default", "web")
        g.add_node("ReplicaSet", "default", "web-rs")
        g.add_node("Pod", "default", "web-pod")
        g.add_edge("Deployment/default/web", "ReplicaSet/default/web-rs", "owns")
        g.add_edge("ReplicaSet/default/web-rs", "Pod/default/web-pod", "owns")
        blast = g.downstream_blast_radius("Deployment", "default", "web")
        assert len(blast) == 2  # RS + Pod

    def test_clear(self):
        g = DependencyGraph()
        g.add_node("Pod", "default", "test")
        g.clear()
        assert g.node_count == 0

    def test_summary(self):
        g = DependencyGraph()
        g.add_node("Pod", "default", "p1")
        g.add_node("Pod", "default", "p2")
        g.add_node("Service", "default", "svc")
        s = g.summary()
        assert s["nodes"] == 3
        assert s["kinds"]["Pod"] == 2

    def test_singleton(self):
        from sre_agent.dependency_graph import get_dependency_graph

        g1 = get_dependency_graph()
        g2 = get_dependency_graph()
        assert g1 is g2
