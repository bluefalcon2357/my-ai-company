"""Shared knowledge store for the company.

A SQLite-backed key/value + append-only log. Every agent can read and write
through the same instance, so e.g. the Sales head can write a lead status
and the CEO can read it on the next turn.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class Memory:
    def __init__(self, path: str | Path = "company.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        REAL NOT NULL,
                actor     TEXT NOT NULL,
                kind      TEXT NOT NULL,
                content   TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def write(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO kv(key, value, updated_at) VALUES(?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, time.time()),
        )
        self._conn.commit()

    def read(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def list_keys(self, prefix: str = "") -> list[str]:
        rows = self._conn.execute(
            "SELECT key FROM kv WHERE key LIKE ? ORDER BY key", (f"{prefix}%",)
        ).fetchall()
        return [r[0] for r in rows]

    def log(self, actor: str, kind: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO log(ts, actor, kind, content) VALUES(?, ?, ?, ?)",
            (time.time(), actor, kind, content),
        )
        self._conn.commit()

    def recent_log(self, limit: int = 50) -> list[tuple[float, str, str, str]]:
        rows = self._conn.execute(
            "SELECT ts, actor, kind, content FROM log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return list(reversed(rows))
