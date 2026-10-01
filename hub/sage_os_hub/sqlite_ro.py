"""Read-only access to Hermes' SQLite files (kanban.db, state.db)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect_ro(path: Path):
    """Short-lived read-only connection. mode=ro means SQLite refuses every write."""
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
