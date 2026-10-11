"""The hub's own SQLite store: persisted events for catch-up, plus the latest panel snapshots.

This is the only database the hub writes, and it lives in sage-os/data/, never under Hermes.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .sync import new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    kind    TEXT NOT NULL,          -- message | task | approval | system
    source  TEXT NOT NULL,          -- adapter name
    type    TEXT NOT NULL,          -- e.g. task.blocked, guard.block, gpu.model
    data    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS panels (
    name    TEXT PRIMARY KEY,
    ts      REAL NOT NULL,
    data    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claude_sessions (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    cwd            TEXT NOT NULL,
    model          TEXT,
    sdk_session_id TEXT,
    created        REAL NOT NULL,
    updated        REAL NOT NULL,
    cost_usd       REAL NOT NULL DEFAULT 0,
    turns          INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chat_items (
    id         TEXT PRIMARY KEY,            -- ci_ + ULID (Y1): sorts by time, unique across devices
    session_id TEXT NOT NULL,
    ts         REAL NOT NULL,
    kind       TEXT NOT NULL,       -- user | text | thinking | tool_use | tool_result | note | error
    data       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chat_items_session ON chat_items (session_id, id);
CREATE TABLE IF NOT EXISTS chat_sessions (      -- chats with OpenAI-compatible models (D22.2)
    id       TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    provider TEXT NOT NULL,
    model    TEXT NOT NULL,
    created  REAL NOT NULL,
    updated  REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path, keep_events: int = 5000):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript("PRAGMA journal_mode=WAL;" + SCHEMA)
        for table in ("claude_sessions", "chat_sessions"):     # Y1.5: deleting leaves a tombstone, not a gap
            if "deleted" not in [r[1] for r in self._db.execute(f"PRAGMA table_info({table})")]:
                self._db.execute(f"ALTER TABLE {table} ADD COLUMN deleted REAL")
        self._db.commit()
        self._lock = threading.Lock()
        self.db, self.lock = self._db, self._lock      # for the change log (Y1.4)
        self._keep = keep_events

    def add_event(self, kind: str, source: str, type_: str, data: dict, ts: float | None = None) -> dict:
        ts = ts or time.time()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO events (ts, kind, source, type, data) VALUES (?,?,?,?,?)",
                (ts, kind, source, type_, json.dumps(data, default=str)))
            eid = cur.lastrowid
            if eid % 200 == 0:
                self._db.execute("DELETE FROM events WHERE id <= ?", (eid - self._keep,))
            self._db.commit()
        return {"id": eid, "ts": ts, "kind": kind, "source": source, "type": type_, "data": data}

    def events_after(self, after: int = 0, limit: int = 500) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, ts, kind, source, type, data FROM events WHERE id > ? ORDER BY id LIMIT ?",
                (after, limit)).fetchall()
        return [{"id": r[0], "ts": r[1], "kind": r[2], "source": r[3], "type": r[4],
                 "data": json.loads(r[5])} for r in rows]

    def recent_events(self, limit: int = 100) -> list[dict]:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()
        return self.events_after(max(0, row[0] - limit), limit)

    def save_panel(self, name: str, data) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO panels (name, ts, data) VALUES (?,?,?)",
                             (name, time.time(), json.dumps(data, default=str)))
            self._db.commit()

    def load_panels(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT name, data FROM panels").fetchall()
        return {n: json.loads(d) for n, d in rows}

    # -- Claude sessions ---------------------------------------------------------------------
    def _upsert(self, table: str, cols: list[str], s: dict) -> None:
        """Insert or update in place: an update never clears a tombstone (a late write can't revive a deleted
        chat), and it's logged as one change (Y1.4)."""
        sets = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
        with self._lock:
            self._db.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                             f"ON CONFLICT(id) DO UPDATE SET {sets}", [s.get(c) for c in cols])
            self._db.commit()

    def _tombstone(self, table: str, sid: str) -> bool:
        with self._lock:
            n = self._db.execute(f"UPDATE {table} SET deleted=? WHERE id=? AND deleted IS NULL",
                                 (time.time(), sid)).rowcount
            self._db.commit()
        return bool(n)

    def upsert_claude_session(self, s: dict) -> None:
        self._upsert("claude_sessions", ["id", "title", "cwd", "model", "sdk_session_id", "created", "updated",
                                         "cost_usd", "turns"], s)

    def delete_claude_session(self, sid: str) -> bool:
        return self._tombstone("claude_sessions", sid)

    def claude_sessions(self) -> list[dict]:
        with self._lock:
            cur = self._db.execute("SELECT * FROM claude_sessions WHERE deleted IS NULL ORDER BY updated DESC")
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    # -- model chats ----------------------------------------------------------------------------
    def upsert_chat_session(self, s: dict) -> None:
        self._upsert("chat_sessions", ["id", "title", "provider", "model", "created", "updated"], s)

    def delete_chat_session(self, sid: str) -> bool:
        return self._tombstone("chat_sessions", sid)

    def chat_sessions(self) -> list[dict]:
        with self._lock:
            cur = self._db.execute("SELECT * FROM chat_sessions WHERE deleted IS NULL ORDER BY updated DESC LIMIT 200")
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def chat_session(self, sid: str) -> dict | None:
        with self._lock:
            cur = self._db.execute("SELECT * FROM chat_sessions WHERE id = ? AND deleted IS NULL", (sid,))
            r = cur.fetchone()
            return dict(zip([d[0] for d in cur.description], r)) if r else None

    def add_chat_item(self, session_id: str, kind: str, data: dict, ts: float | None = None) -> dict:
        ts = ts or time.time()
        iid = new_id("ci_")
        with self._lock:
            self._db.execute("INSERT INTO chat_items (id, session_id, ts, kind, data) VALUES (?,?,?,?,?)",
                             (iid, session_id, ts, kind, json.dumps(data, default=str)))
            self._db.commit()
        return {"id": iid, "ts": ts, "kind": kind, "data": data}

    def chat_items(self, session_id: str, limit: int = 500) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, ts, kind, data FROM (SELECT * FROM chat_items WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?) ORDER BY id", (session_id, limit)).fetchall()
        return [{"id": r[0], "ts": r[1], "kind": r[2], "data": json.loads(r[3])} for r in rows]

    def close(self) -> None:
        self._db.close()
