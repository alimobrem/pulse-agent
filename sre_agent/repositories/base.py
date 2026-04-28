"""Base repository with lazy database access (sync and async)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..async_db import AsyncDatabase
    from ..db import Database


class BaseRepository:
    """Base class for domain-specific repositories.

    Provides lazy access to the database singleton via the ``db`` property
    (sync, psycopg2) and the ``async_db`` property (async, asyncpg).

    When no explicit ``Database`` is provided, the property delegates to
    ``get_database()`` on every access so that ``reset_database()`` in tests
    is respected without needing per-repository reset functions.
    """

    def __init__(self, db: Database | None = None):
        self._db = db
        self._db_injected = db is not None

    @property
    def db(self) -> Database:
        if self._db_injected:
            assert self._db is not None  # guaranteed by __init__ when _db_injected=True
            return self._db
        from ..db import get_database

        return get_database()

    async def get_async_db(self) -> AsyncDatabase:
        """Return the async database singleton.

        Always delegates to ``get_async_database()`` so that
        ``reset_async_database()`` is respected without stale caches.
        """
        from ..async_db import get_async_database

        return await get_async_database()
