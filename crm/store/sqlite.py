from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from crm.store.migrations import apply_schema


class SqliteSession:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, query: str, params: Iterable[Any] | None = None) -> None:
        self._conn.execute(query, params or [])

    def fetch_all(self, query: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
        cur = self._conn.execute(query, params or [])
        return cur.fetchall()

    def fetch_one(self, query: str, params: Iterable[Any] | None = None) -> sqlite3.Row | None:
        cur = self._conn.execute(query, params or [])
        return cur.fetchone()

    def upsert_mirror_state(
        self,
        table_name: str,
        external_id: str,
        record_id: str | None,
        mirror_version: int,
        mirror_updated_at: str,
    ) -> None:
        query = (
            "INSERT INTO mirror_state (table_name, external_id, record_id, mirror_version, mirror_updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(table_name, external_id) DO UPDATE SET "
            "record_id=excluded.record_id, mirror_version=excluded.mirror_version, "
            "mirror_updated_at=excluded.mirror_updated_at"
        )
        self.execute(query, (table_name, external_id, record_id, mirror_version, mirror_updated_at))

    def get_mirror_state(self, table_name: str, external_id: str) -> sqlite3.Row | None:
        return self.fetch_one(
            "SELECT * FROM mirror_state WHERE table_name = ? AND external_id = ?",
            (table_name, external_id),
        )


class SqliteStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def session(self) -> SqliteSession:
        with self.connect() as conn:
            yield SqliteSession(conn)

    def apply_schema(self, schema_path: Path) -> None:
        with self.connect() as conn:
            apply_schema(conn, schema_path)

    def execute(self, query: str, params: Iterable[Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(query, params or [])

    def fetch_all(self, query: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(query, params or [])
            return cur.fetchall()

    def fetch_one(self, query: str, params: Iterable[Any] | None = None) -> sqlite3.Row | None:
        with self.connect() as conn:
            cur = conn.execute(query, params or [])
            return cur.fetchone()

    def upsert_mirror_state(
        self,
        table_name: str,
        external_id: str,
        record_id: str | None,
        mirror_version: int,
        mirror_updated_at: str,
    ) -> None:
        with self.session() as session:
            session.upsert_mirror_state(
                table_name, external_id, record_id, mirror_version, mirror_updated_at
            )

    def get_mirror_state(self, table_name: str, external_id: str) -> sqlite3.Row | None:
        with self.session() as session:
            return session.get_mirror_state(table_name, external_id)
