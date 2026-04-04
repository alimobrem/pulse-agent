"""Tests for the agent orchestrator — intent classification and config building."""

from __future__ import annotations

from sre_agent.orchestrator import build_orchestrated_config, classify_intent


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
