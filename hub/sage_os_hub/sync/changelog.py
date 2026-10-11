"""The change log (Y1.4, D28): every change to a synced table, written alongside the row in the same
transaction, as an append-only entry that sync (Y4) will ship to other devices.

How: each synced database gets a `changes` table, and the hub's connection gets TEMP triggers on every synced
table (sync/manifest.py) that append an entry on insert, update and delete. Triggers can't be forgotten by a new
write path, and being TEMP they live only on the hub's own connection: the database files carry no trigger
that another program would trip over.

An entry: id (a ULID: orders entries), device, ts, stream (the table), record (its key), op (upsert / delete),
data (the whole row as JSON; BLOBs as {"$hex": ...}; REALs exact).

Merging (apply): entries are idempotent (the id is the primary key) and a record takes the newest entry for it,
whatever order entries arrive in, so two devices that have seen the same entries hold the same rows. Rows are
last-writer-wins as a whole; per-field merging is a later option.
"""
from __future__ import annotations

import json
import math
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


def _real(v: float) -> str:
    """A REAL as exact JSON: SQLite's own JSON keeps only 15 digits, which changes timestamps on the way
    through the log (found by the Y1.7 gate)."""
    return repr(v) if math.isfinite(v) else "null"


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class ChangeLog:
    def __init__(self, con: sqlite3.Connection, db_name: str, device_id: str, lock: threading.RLock | None = None):
        self.con, self.db_name, self.device_id = con, db_name, device_id
        self.lock = lock or threading.RLock()
        self._on = True
        self._columns: dict[str, list[str]] = {}
        self.streams = manifest.synced_tables().get(db_name, [])
        con.create_function("sage_change_id", 0, lambda: ulid())
        con.create_function("sage_device", 0, lambda: self.device_id)
        con.create_function("sage_now", 0, time.time)
        con.create_function("sage_logging", 0, lambda: 1 if self._on else 0)
        con.create_function("sage_real", 1, _real, deterministic=True)
        with self.lock:
            con.executescript(SCHEMA)
            for table in self.streams:
                self._triggers(table)
            con.commit()

    # -- writing ------------------------------------------------------------------------------------
    def columns(self, table: str) -> list[str]:
        """Read once per table: columns are added only at start-up, before the triggers are made."""
        if table not in self._columns:
            self._columns[table] = [r[1] for r in self.con.execute(f"PRAGMA main.table_info({_q(table)})")]
        return self._columns[table]

    def _row_json(self, table: str, ref: str) -> str:
        parts = []
        for c in self.columns(table):
            v = f"{ref}.{_q(c)}"
            parts.append(f"'{c}', CASE typeof({v}) WHEN 'blob' THEN json_object('$hex', hex({v})) "
                         f"WHEN 'real' THEN json(sage_real({v})) ELSE {v} END")
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

    def seed(self) -> dict[str, int]:
        """Log every existing row as created on this device (Y1.6), for tables with nothing logged yet.
        -> rows logged per table."""
        out = {}
        with self.lock:
            for table in self.streams:
                if self.con.execute("SELECT 1 FROM changes WHERE stream=? LIMIT 1", (table,)).fetchone():
                    continue
                key = ", ".join(map(_q, manifest.KEYS[table]))
                cur = self.con.execute(
                    f"INSERT INTO changes(id, device, ts, stream, record, op, data) SELECT sage_change_id(), "
                    f"sage_device(), sage_now(), '{table}', {self._record(table, 'r')}, 'upsert', "
                    f"{self._row_json(table, 'r')} FROM main.{_q(table)} AS r ORDER BY {key}")
                out[table] = cur.rowcount
            self.con.commit()
        return out

    # -- reading and merging ------------------------------------------------------------------------
    def entries(self, after: str = "", device: str | None = None, limit: int | None = None) -> list[dict]:
        """Entries after `after`, oldest first; all of them unless `limit` is given (then page with `after`)."""
        sql, args = "SELECT id, device, ts, stream, record, op, data FROM changes WHERE id > ?", [after]
        if device:
            sql += " AND device = ?"
            args.append(device)
        with self.lock:
            rows = self.con.execute(sql + " ORDER BY id LIMIT ?", (*args, -1 if limit is None else limit)).fetchall()
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
                    self._keep_tombstone(e)     # a newer change is already here; a delete still counts
                    continue
                self._put(e)
            self.con.commit()
        return new

    def _where(self, e: dict) -> tuple[str, list]:
        key = manifest.KEYS[e["stream"]]
        vals = [e["record"]] if len(key) == 1 else json.loads(e["record"])
        return " AND ".join(f"{_q(k)} = ?" for k in key), vals

    def _deleted(self, e: dict):
        if "deleted" not in self.columns(e["stream"]):
            return None
        where, vals = self._where(e)
        row = self.con.execute(f"SELECT deleted FROM {_q(e['stream'])} WHERE {where}", vals).fetchone()
        return row[0] if row else None

    def _keep_tombstone(self, e: dict) -> None:
        """Deletes win (Y1.5): an older change that deleted the record still deletes it, with the earliest
        delete time on every device, so a record never lives on one device and not on another."""
        gone = (e.get("data") or {}).get("deleted")
        if e["op"] != "upsert" or gone is None or "deleted" not in self.columns(e["stream"]):
            return
        where, vals = self._where(e)
        self.con.execute(f"UPDATE {_q(e['stream'])} SET deleted = min(coalesce(deleted, ?), ?) WHERE {where}",
                         [gone, gone, *vals])

    def _put(self, e: dict) -> None:
        table = e["stream"]
        if e["op"] == "delete":
            where, vals = self._where(e)
            self.con.execute(f"DELETE FROM {_q(table)} WHERE {where}", vals)
            return
        have = set(self.columns(table))
        row = {k: (bytes.fromhex(v["$hex"]) if isinstance(v, dict) and "$hex" in v else v)
               for k, v in e["data"].items() if k in have}
        here = self._deleted(e)
        if here is not None:                            # deletes win (Y1.5): the earliest delete time
            row["deleted"] = here if row.get("deleted") is None else min(here, row["deleted"])
        cols = list(row)
        self.con.execute(f"INSERT OR REPLACE INTO {_q(table)} ({', '.join(map(_q, cols))}) "
                         f"VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])
