"""Tests for the agent orchestrator — intent classification and config building."""

from __future__ import annotations

from sre_agent.orchestrator import build_orchestrated_config, classify_intent, fix_typos


class TestClassifyIntent:
    def test_sre_crashlooping(self):
        mode, is_strong = classify_intent("why are pods crashlooping")
        assert mode == "sre"
        assert is_strong is True

    def test_security_rbac(self):
        mode, is_strong = classify_intent("check RBAC permissions")
        assert mode == "security"
        assert is_strong is True

    def test_both_full_audit(self):
        mode, is_strong = classify_intent("full cluster audit")
        assert mode == "both"
        assert is_strong is True

    def test_default_sre(self):
        mode, is_strong = classify_intent("hello")
        assert mode == "sre"
        assert is_strong is False  # no keyword matches = weak/default

    def test_mixed_keywords_more_security(self):
        mode, _ = classify_intent("check network policy and service account permissions")
        assert mode == "security"

    def test_mixed_keywords_more_sre(self):
        mode, _ = classify_intent("pod restart and node drain and check logs")
        assert mode == "sre"

    def test_both_scan_cluster(self):
        mode, _ = classify_intent("scan the cluster for issues")
        assert mode == "both"

    def test_both_production_readiness(self):
        mode, _ = classify_intent("production readiness review")
        assert mode == "both"

    def test_case_insensitive(self):
        mode, _ = classify_intent("CHECK RBAC PERMISSIONS")
        assert mode == "security"

    def test_empty_string(self):
        mode, is_strong = classify_intent("")
        assert mode == "sre"
        assert is_strong is False

    def test_view_designer_strong(self):
        mode, is_strong = classify_intent("create a dashboard for my cluster")
        assert mode == "view_designer"
        assert is_strong is True

    def test_followup_weak(self):
        """A follow-up like 'yes build it' should be weak (no keywords)."""
        mode, is_strong = classify_intent("yes, build it")
        assert mode == "sre"  # default fallback
        assert is_strong is False  # caller should keep previous mode


class TestBuildOrchestratedConfig:
    def test_sre_config(self):
        config = build_orchestrated_config("sre")
        assert "system_prompt" in config
        assert "tool_defs" in config
        assert "tool_map" in config
        assert "write_tools" in config
        assert len(config["write_tools"]) > 0

    def test_security_config(self):
        config = build_orchestrated_config("security")
        assert config["write_tools"] == set()
        assert "Security" in config["system_prompt"]

    def test_both_config_merges_tools(self):
        config = build_orchestrated_config("both")
        # Should have tools from both SRE and security
        sre_config = build_orchestrated_config("sre")
        sec_config = build_orchestrated_config("security")
        # Merged map should contain all keys from both
        for key in sre_config["tool_map"]:
            assert key in config["tool_map"]
        for key in sec_config["tool_map"]:
            assert key in config["tool_map"]
        # Prompt should mention security scanning
        assert "security scanning tools" in config["system_prompt"]

    def test_both_config_has_write_tools(self):
        config = build_orchestrated_config("both")
        assert len(config["write_tools"]) > 0


class TestFixTypos:
    def test_deployment_typos(self):
        assert fix_typos("list depoyments") == "list deployments"
        assert fix_typos("show me deploymnet status") == "show me deployment status"
        assert fix_typos("why is my deployemnt failing") == "why is my deployment failing"

    def test_namespace_typos(self):
        assert fix_typos("pods in namepsace production") == "pods in namespace production"
        assert fix_typos("switch namspace") == "switch namespace"

    def test_service_typos(self):
        assert fix_typos("list serivces") == "list services"
        assert fix_typos("describe sevice nginx") == "describe service nginx"

    def test_security_typos(self):
        assert fix_typos("check for vulerabilities") == "check for vulnerabilities"
        assert fix_typos("scan for privilige escalation") == "scan for privilege escalation"
        assert fix_typos("netwrok policy audit") == "network policy audit"

    def test_sre_typos(self):
        assert fix_typos("pods are crashloping") == "pods are crashlooping"
        assert fix_typos("query promethues metrics") == "query prometheus metrics"
        assert fix_typos("rollbak the deployment") == "rollback the deployment"
        assert fix_typos("scael to 5 replicas") == "scale to 5 replicas"

    def test_dashboard_typos(self):
        assert fix_typos("create a dahsboard") == "create a dashboard"
        assert fix_typos("add a widegt") == "add a widget"

    def test_preserves_capitalization(self):
        assert fix_typos("Depoyment is failing") == "Deployment is failing"

    def test_preserves_correct_words(self):
        assert fix_typos("list pods in namespace default") == "list pods in namespace default"
        assert fix_typos("show deployments") == "show deployments"

    def test_empty_string(self):
        assert fix_typos("") == ""

    def test_multiple_typos_in_one_query(self):
        result = fix_typos("depoyment in namepsace has serivce issues")
        assert result == "deployment in namespace has service issues"

    def test_typos_improve_classification(self):
        """Verify that fixing typos leads to correct intent classification."""
        # Without fix: 'vulerability' might not match 'vulnerability' keyword
        raw = "scan for vulerabilities and compliace issues"
        fixed = fix_typos(raw)
        mode, is_strong = classify_intent(fixed)
        assert mode == "security"
        assert is_strong is True

    def test_dashboard_typo_routes_to_view_designer(self):
        raw = "create a dahsboard for my cluster"
        fixed = fix_typos(raw)
        mode, _ = classify_intent(fixed)
        assert mode == "view_designer"
