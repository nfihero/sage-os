"""The change log (Y1.4, D28): every change to a synced table, written alongside the row in the same
transaction, as an append-only entry that sync (Y4) will ship to other devices.

How: each synced database gets a `changes` table, and the hub's connection gets TEMP triggers on every synced
table (sync/manifest.py) that append an entry on insert, update and delete. Triggers can't be forgotten by a new
write path, and being TEMP they live only on the hub's own connection: the database files carry no trigger
that another program would trip over.

An entry: id (a ULID: orders entries), device, ts, stream (the table), record (its key), op (upsert / delete),
data (the whole row as JSON; BLOBs as {"$hex": ...}).

Merging (apply): entries are idempotent (the id is the primary key) and a record takes the newest entry for it,
whatever order entries arrive in, so two devices that have seen the same entries hold the same rows. Rows are
last-writer-wins as a whole; per-field merging is a later option.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from . import manifest
from .ids import ulid

SCHEMA = """
CREATE TABLE IF NOT EXISTS changes(
  id TEXT PRIMARY KEY, device TEXT NOT NULL, ts REAL NOT NULL, stream TEXT NOT NULL, record TEXT NOT NULL,
  op TEXT NOT NULL, data TEXT);
CREATE INDEX IF NOT EXISTS changes_record ON changes(stream, record, id);
"""


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class ChangeLog:
    def __init__(self, con: sqlite3.Connection, db_name: str, device_id: str, lock: threading.RLock | None = None):
        self.con, self.db_name, self.device_id = con, db_name, device_id
        self.lock = lock or threading.RLock()
        self._on = True
        self.streams = manifest.synced_tables().get(db_name, [])
        con.create_function("sage_change_id", 0, lambda: ulid())
        con.create_function("sage_device", 0, lambda: self.device_id)
        con.create_function("sage_now", 0, time.time)
        con.create_function("sage_logging", 0, lambda: 1 if self._on else 0)
        with self.lock:
            con.executescript(SCHEMA)
            for table in self.streams:
                self._triggers(table)
            con.commit()

    # -- writing ------------------------------------------------------------------------------------
    def columns(self, table: str) -> list[str]:
        return [r[1] for r in self.con.execute(f"PRAGMA main.table_info({_q(table)})")]

    def _row_json(self, table: str, ref: str) -> str:
        parts = []
        for c in self.columns(table):
            v = f"{ref}.{_q(c)}"
            parts.append(f"'{c}', CASE WHEN typeof({v}) = 'blob' THEN json_object('$hex', hex({v})) ELSE {v} END")
        return f"json_object({', '.join(parts)})"

    def _record(self, table: str, ref: str) -> str:
        key = manifest.KEYS[table]
        if len(key) == 1:
            return f"CAST({ref}.{_q(key[0])} AS TEXT)"
        return "json_array(" + ", ".join(f"{ref}.{_q(k)}" for k in key) + ")"

    def _triggers(self, table: str) -> None:
        """(Re)made on every start, so a column added since is in the logged row."""
        t = _q(table)
        for op, when, ref, data in (("insert", "INSERT", "NEW", self._row_json(table, "NEW")),
                                    ("update", "UPDATE", "NEW", self._row_json(table, "NEW")),
                                    ("delete", "DELETE", "OLD", "NULL")):
            name = _q(f"sync_{table}_{op}")
            kind = "delete" if op == "delete" else "upsert"
            self.con.execute(f"DROP TRIGGER IF EXISTS temp.{name}")
            self.con.execute(
                f"CREATE TEMP TRIGGER {name} AFTER {when} ON main.{t} WHEN sage_logging() BEGIN "
                f"INSERT INTO changes(id, device, ts, stream, record, op, data) VALUES "
                f"(sage_change_id(), sage_device(), sage_now(), '{table}', {self._record(table, ref)}, '{kind}', {data}); END")

    @contextmanager
    def quiet(self):
        """Writes inside this block aren't logged (a migration, or entries arriving from another device). Holds
        the owner's lock, so no other write slips in unlogged meanwhile; don't nest it in that lock if it isn't
        reentrant."""
        with self.lock:
            self._on = False
            try:
                yield
            finally:
                self._on = True

    # -- reading and merging ------------------------------------------------------------------------
    def entries(self, after: str = "", device: str | None = None, limit: int = 10_000) -> list[dict]:
        sql, args = "SELECT id, device, ts, stream, record, op, data FROM changes WHERE id > ?", [after]
        if device:
            sql += " AND device = ?"
            args.append(device)
        with self.lock:
            rows = self.con.execute(sql + " ORDER BY id LIMIT ?", (*args, limit)).fetchall()
        return [{"id": r[0], "device": r[1], "ts": r[2], "stream": r[3], "record": r[4], "op": r[5],
                 "data": json.loads(r[6]) if r[6] is not None else None} for r in rows]

    def apply(self, entries: list[dict]) -> int:
        """Merge entries from another device. -> how many were new. Safe to repeat and in any order."""
        new = 0
        with self.quiet():
            for e in sorted(entries, key=lambda e: e["id"]):
                if e["stream"] not in self.streams:
                    continue
                ulid.observe(e["id"])           # our next change sorts after everything we've seen
                cur = self.con.execute(
                    "INSERT OR IGNORE INTO changes(id, device, ts, stream, record, op, data) VALUES (?,?,?,?,?,?,?)",
                    (e["id"], e["device"], e["ts"], e["stream"], e["record"], e["op"],
                     json.dumps(e["data"]) if e["data"] is not None else None))
                if not cur.rowcount:
                    continue                    # seen before
                new += 1
                latest = self.con.execute("SELECT max(id) FROM changes WHERE stream=? AND record=?",
                                          (e["stream"], e["record"])).fetchone()[0]
                if latest != e["id"]:
                    continue                    # a newer change to this record is already here
                self._put(e)
            self.con.commit()
        return new

    def _put(self, e: dict) -> None:
        table, key = e["stream"], manifest.KEYS[e["stream"]]
        if e["op"] == "delete":
            vals = [e["record"]] if len(key) == 1 else json.loads(e["record"])
            self.con.execute(f"DELETE FROM {_q(table)} WHERE " + " AND ".join(f"{_q(k)} = ?" for k in key), vals)
            return
        have = set(self.columns(table))
        row = {k: (bytes.fromhex(v["$hex"]) if isinstance(v, dict) and "$hex" in v else v)
               for k, v in e["data"].items() if k in have}
        cols = list(row)
        self.con.execute(f"INSERT OR REPLACE INTO {_q(table)} ({', '.join(map(_q, cols))}) "
                         f"VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])
