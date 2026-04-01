"""Tests for outcome-based eval analysis."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from sre_agent.db import Database, get_database, reset_database, set_database
from sre_agent.evals.outcomes import analyze_windows
from tests.conftest import _TEST_DB_URL


@pytest.fixture(autouse=True)
def _setup_actions_table():
    """Ensure actions table exists and is clean."""
    db = Database(_TEST_DB_URL)
    set_database(db)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY,
            timestamp BIGINT,
            status TEXT,
            duration_ms INTEGER,
            input TEXT
        );
        """
    )
    db.execute("TRUNCATE actions RESTART IDENTITY CASCADE")
    db.commit()
    yield
    reset_database()


def _insert_action(action_id: str, timestamp_ms: int, status: str, duration_ms: int, inp: dict):
    db = get_database()
    db.execute(
        "INSERT INTO actions (id, timestamp, status, duration_ms, input) VALUES (%s, %s, %s, %s, %s)",
        (action_id, timestamp_ms, status, duration_ms, json.dumps(inp)),
    )
    db.commit()


def test_outcome_report_detects_regression():
    day = 86_400_000
    real_now = int(time.time() * 1000)

    # baseline window: [now-2d, now-1d)
    _insert_action("b1", real_now - int(1.8 * day), "completed", 100, {"confidence": 0.8})
    _insert_action("b2", real_now - int(1.7 * day), "completed", 120, {"confidence": 0.9})

    # current window: [now-1d, now)
    _insert_action("c1", real_now - int(0.8 * day), "failed", 1200, {"confidence": 0.9})
    _insert_action("c2", real_now - int(0.7 * day), "rolled_back", 1500, {"confidence": 0.7})

    report = analyze_windows(db_path=_TEST_DB_URL, current_days=1, baseline_days=1)
    assert report["current"]["total_actions"] == 2
    assert report["baseline"]["total_actions"] == 2
    assert report["regressions"]["success_drop"] is True
    assert report["gate_passed"] is False


def test_outcome_report_handles_empty_db():
    report = analyze_windows(db_path=_TEST_DB_URL, current_days=7, baseline_days=7)
    assert report["current"]["total_actions"] == 0
    assert report["baseline"]["total_actions"] == 0


def test_outcome_report_uses_policy_file_thresholds(tmp_path: Path):
    day = 86_400_000
    now = int(time.time() * 1000)

    _insert_action("b1", now - int(1.8 * day), "completed", 100, {"confidence": 0.8})
    _insert_action("c1", now - int(0.8 * day), "completed", 180, {"confidence": 0.8})

    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "version: 2",
                "thresholds:",
                "  success_rate_delta_min: -0.10",
                "  rollback_rate_delta_max: 0.10",
                "  p95_duration_ms_delta_max: 10.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = analyze_windows(db_path=_TEST_DB_URL, current_days=1, baseline_days=1, policy_path=str(policy))
    assert report["policy"]["version"] == 2
    assert report["regressions"]["latency_increase"] is True
