"""Tests for tool usage tracking — DB functions, recording, querying."""

from __future__ import annotations

from sre_agent.db import Database, reset_database, set_database
from sre_agent.db_migrations import run_migrations

from .conftest import _TEST_DB_URL


def _make_test_db() -> Database:
    db = Database(_TEST_DB_URL)
    db.execute("DROP TABLE IF EXISTS tool_usage CASCADE")
    db.execute("DROP TABLE IF EXISTS tool_turns CASCADE")
    db.commit()
    return db


class TestToolUsageTables:
    def test_migration_creates_tables(self):
        db = _make_test_db()
        db.execute("DELETE FROM schema_migrations WHERE version >= 2")
        db.commit()
        set_database(db)
        run_migrations(db)

        row = db.fetchone(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tool_usage') AS exists"
        )
        assert row["exists"] is True

        row = db.fetchone(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tool_turns') AS exists"
        )
        assert row["exists"] is True
        reset_database()

    def test_tool_usage_insert(self):
        db = _make_test_db()
        db.execute("DELETE FROM schema_migrations WHERE version >= 2")
        db.commit()
        set_database(db)
        run_migrations(db)

        db.execute(
            "INSERT INTO tool_usage (session_id, turn_number, agent_mode, tool_name, tool_category, "
            "input_summary, status, duration_ms, result_bytes, requires_confirmation, was_confirmed) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                "sess-1",
                1,
                "sre",
                "list_pods",
                "diagnostics",
                '{"namespace": "default"}',
                "success",
                342,
                4820,
                False,
                None,
            ),
        )
        db.commit()

        row = db.fetchone("SELECT * FROM tool_usage WHERE session_id = %s", ("sess-1",))
        assert row is not None
        assert row["tool_name"] == "list_pods"
        assert row["status"] == "success"
        assert row["duration_ms"] == 342
        reset_database()

    def test_tool_turns_insert(self):
        db = _make_test_db()
        db.execute("DELETE FROM schema_migrations WHERE version >= 2")
        db.commit()
        set_database(db)
        run_migrations(db)

        db.execute(
            "INSERT INTO tool_turns (session_id, turn_number, agent_mode, query_summary, tools_offered, tools_called) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("sess-1", 1, "sre", "show pods", ["list_pods", "get_events"], ["list_pods"]),
        )
        db.commit()

        row = db.fetchone("SELECT * FROM tool_turns WHERE session_id = %s", ("sess-1",))
        assert row is not None
        assert row["tools_offered"] == ["list_pods", "get_events"]
        assert row["tools_called"] == ["list_pods"]
        reset_database()

    def test_tool_turns_unique_constraint(self):
        db = _make_test_db()
        db.execute("DELETE FROM schema_migrations WHERE version >= 2")
        db.commit()
        set_database(db)
        run_migrations(db)

        db.execute(
            "INSERT INTO tool_turns (session_id, turn_number, agent_mode, query_summary, tools_offered, tools_called) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("sess-1", 1, "sre", "q1", [], []),
        )
        db.commit()

        # Upsert should work
        db.execute(
            "INSERT INTO tool_turns (session_id, turn_number, agent_mode, query_summary, tools_offered, tools_called) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (session_id, turn_number) DO UPDATE SET tools_called = EXCLUDED.tools_called",
            ("sess-1", 1, "sre", "q1", [], ["list_pods"]),
        )
        db.commit()

        row = db.fetchone("SELECT * FROM tool_turns WHERE session_id = %s", ("sess-1",))
        assert row["tools_called"] == ["list_pods"]
        reset_database()
