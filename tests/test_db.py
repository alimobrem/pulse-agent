"""Tests for sre_agent.db — Database abstraction layer."""

from __future__ import annotations

import os
import tempfile

from sre_agent.db import Database, get_database, reset_database, set_database

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqlite_db(tmp_path: str) -> Database:
    path = os.path.join(tmp_path, "test.db")
    return Database(f"sqlite:///{path}")


# ---------------------------------------------------------------------------
# Database with SQLite URL
# ---------------------------------------------------------------------------


class TestDatabaseSQLite:
    def test_create_table_and_insert(self, tmp_path):
        db = _make_sqlite_db(str(tmp_path))
        db.execute("CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, val INTEGER)")
        db.execute("INSERT INTO t (id, val) VALUES (?, ?)", ("a", 1))
        db.commit()
        row = db.fetchone("SELECT * FROM t WHERE id = ?", ("a",))
        assert row is not None
        assert row["id"] == "a"
        assert row["val"] == 1
        db.close()

    def test_fetchall(self, tmp_path):
        db = _make_sqlite_db(str(tmp_path))
        db.execute("CREATE TABLE t (id TEXT, n INTEGER)")
        for i in range(5):
            db.execute("INSERT INTO t VALUES (?, ?)", (f"r{i}", i))
        db.commit()
        rows = db.fetchall("SELECT * FROM t ORDER BY n")
        assert len(rows) == 5
        assert rows[0]["n"] == 0
        assert rows[4]["n"] == 4
        db.close()

    def test_fetchone_returns_none(self, tmp_path):
        db = _make_sqlite_db(str(tmp_path))
        db.execute("CREATE TABLE t (id TEXT)")
        db.commit()
        assert db.fetchone("SELECT * FROM t") is None
        db.close()

    def test_executescript(self, tmp_path):
        db = _make_sqlite_db(str(tmp_path))
        db.executescript(
            "CREATE TABLE IF NOT EXISTS a (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT);"
            "CREATE TABLE IF NOT EXISTS b (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT);"
        )
        db.execute("INSERT INTO a (v) VALUES (?)", ("x",))
        db.execute("INSERT INTO b (v) VALUES (?)", ("y",))
        db.commit()
        assert db.fetchone("SELECT v FROM a")["v"] == "x"
        assert db.fetchone("SELECT v FROM b")["v"] == "y"
        db.close()

    def test_lastrowid(self, tmp_path):
        db = _make_sqlite_db(str(tmp_path))
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
        db.execute("INSERT INTO t (v) VALUES (?)", ("hello",))
        db.commit()
        assert db.lastrowid >= 1
        db.close()

    def test_plain_path_url(self, tmp_path):
        """Database accepts a bare file path (no sqlite:/// prefix)."""
        path = os.path.join(str(tmp_path), "bare.db")
        db = Database(path)
        assert not db.is_postgres
        db.execute("CREATE TABLE t (id TEXT)")
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# Query translation
# ---------------------------------------------------------------------------


class TestQueryTranslation:
    def test_sqlite_keeps_question_marks(self):
        db = Database(":memory:")
        assert db._translate_query("SELECT * WHERE x = ?") == "SELECT * WHERE x = ?"
        db.close()

    def test_postgres_replaces_question_marks(self):
        """Verify translation without actually connecting to PostgreSQL."""
        db = Database(":memory:")
        db.is_postgres = True  # pretend
        result = db._translate_query("INSERT INTO t VALUES (?, ?, ?)")
        assert result == "INSERT INTO t VALUES (%s, %s, %s)"
        db.close()


# ---------------------------------------------------------------------------
# Schema translation
# ---------------------------------------------------------------------------


class TestSchemaTranslation:
    def test_autoincrement_to_serial(self):
        db = Database(":memory:")
        db.is_postgres = True
        result = db._translate_schema("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
        assert "SERIAL PRIMARY KEY" in result
        assert "AUTOINCREMENT" not in result
        db.close()

    def test_pragma_removed(self):
        db = Database(":memory:")
        db.is_postgres = True
        result = db._translate_schema("PRAGMA journal_mode=WAL;")
        assert "PRAGMA" not in result
        db.close()

    def test_insert_or_replace_translated(self):
        db = Database(":memory:")
        db.is_postgres = True
        result = db._translate_schema("INSERT OR REPLACE INTO t VALUES (1)")
        assert "INSERT INTO" in result
        assert "OR REPLACE" not in result
        db.close()

    def test_sqlite_schema_unchanged(self):
        db = Database(":memory:")
        ddl = "CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT)"
        assert db._translate_schema(ddl) == ddl
        db.close()


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------


class TestSingleton:
    def setup_method(self):
        reset_database()

    def teardown_method(self):
        reset_database()

    def test_get_database_returns_same_instance(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            url = f"sqlite:///{td}/singleton.db"
            monkeypatch.setenv("PULSE_AGENT_DATABASE_URL", url)
            db1 = get_database()
            db2 = get_database()
            assert db1 is db2

    def test_set_database_overrides(self):
        db = Database(":memory:")
        set_database(db)
        assert get_database() is db
        db.close()

    def test_reset_database_clears(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            url = f"sqlite:///{td}/reset.db"
            monkeypatch.setenv("PULSE_AGENT_DATABASE_URL", url)
            db1 = get_database()
            reset_database()
            db2 = get_database()
            assert db1 is not db2


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_healthy_connection(self):
        db = Database(":memory:")
        assert db.health_check() is True
        db.close()

    def test_closed_connection(self):
        db = Database(":memory:")
        db.close()
        assert db.health_check() is False
