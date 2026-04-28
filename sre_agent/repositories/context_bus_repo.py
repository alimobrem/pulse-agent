"""Context bus repository -- context_entries database operations.

Covers: context_bus.py (ensure_tables, publish, get_context_for).
"""

from __future__ import annotations

import logging

from .. import db_schema
from .base import BaseRepository

logger = logging.getLogger("pulse_agent.context_bus")


class ContextBusRepository(BaseRepository):
    """Database operations for the shared context bus."""

    _tables_ensured = False

    def ensure_tables(self) -> None:
        """Create context_entries table if it doesn't exist."""
        if ContextBusRepository._tables_ensured:
            return
        try:
            self.db.executescript(db_schema.CONTEXT_ENTRIES_SCHEMA)
            self.db.executescript(
                "CREATE INDEX IF NOT EXISTS idx_context_entries_ts ON context_entries(timestamp DESC);\n"
                "CREATE INDEX IF NOT EXISTS idx_context_entries_ns ON context_entries(namespace);\n"
            )
            ContextBusRepository._tables_ensured = True
        except Exception as e:
            logger.warning("Failed to ensure context_entries table: %s", e)

    def insert_entry(
        self,
        source: str,
        category: str,
        summary: str,
        details_json: str,
        timestamp_ms: int,
        namespace: str,
        resources_json: str,
    ) -> None:
        """Insert a context entry."""
        self.db.execute(
            """INSERT INTO context_entries
               (source, category, summary, details, timestamp, namespace, resources)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source, category, summary, details_json, timestamp_ms, namespace, resources_json),
        )

    def prune_old_entries(self, max_entries: int) -> None:
        """Delete entries beyond the max count."""
        self.db.execute(
            """DELETE FROM context_entries WHERE id NOT IN (
               SELECT id FROM context_entries ORDER BY id DESC LIMIT ?
            )""",
            (max_entries,),
        )

    def commit(self) -> None:
        """Commit the current transaction."""
        self.db.commit()

    def fetch_entries(self, where: str, params: tuple, limit: int) -> list[dict]:
        """Fetch context entries with a WHERE clause."""
        return self.db.fetchall(
            f"SELECT * FROM context_entries WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            params + (limit,),
        )

    def fetch_context_entry_count(self) -> dict | None:
        """Count context_entries rows (for debug endpoint)."""
        return self.db.fetchone("SELECT COUNT(*) AS cnt FROM context_entries")


# -- Singleton ---------------------------------------------------------------

_context_bus_repo: ContextBusRepository | None = None


def get_context_bus_repo() -> ContextBusRepository:
    """Return the module-level ContextBusRepository singleton."""
    global _context_bus_repo
    if _context_bus_repo is None:
        _context_bus_repo = ContextBusRepository()
    return _context_bus_repo
