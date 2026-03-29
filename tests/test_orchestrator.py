"""Tests for the agent orchestrator — intent classification and config building."""

from __future__ import annotations

from sre_agent.orchestrator import build_orchestrated_config, classify_intent


class TestClassifyIntent:
    def test_sre_crashlooping(self):
        assert classify_intent("why are pods crashlooping") == "sre"

    def test_security_rbac(self):
        assert classify_intent("check RBAC permissions") == "security"

    def test_both_full_audit(self):
        assert classify_intent("full cluster audit") == "both"

    def test_default_sre(self):
        assert classify_intent("hello") == "sre"

    def test_mixed_keywords_more_security(self):
        assert classify_intent("check network policy and service account permissions") == "security"

    def test_mixed_keywords_more_sre(self):
        assert classify_intent("pod restart and node drain and check logs") == "sre"

    def test_both_scan_cluster(self):
        assert classify_intent("scan the cluster for issues") == "both"

    def test_both_production_readiness(self):
        assert classify_intent("production readiness review") == "both"

    def test_case_insensitive(self):
        assert classify_intent("CHECK RBAC PERMISSIONS") == "security"

    def test_empty_string(self):
        assert classify_intent("") == "sre"


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
