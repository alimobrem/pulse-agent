"""Verify all version references agree."""

from importlib.metadata import version

import pytest


def test_api_version_matches_package():
    """The FastAPI app version should match the installed package version."""
    try:
        from sre_agent.api import app
    except ImportError:
        pytest.skip("fastapi not installed")
    assert app.version == version("openshift-sre-agent")
