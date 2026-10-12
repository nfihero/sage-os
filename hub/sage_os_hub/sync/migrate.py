"""The one-time move to ULIDs (Y1.6, D28): every synced record gets a fresh ULID and every reference to it
follows; then each existing row goes into the change log as created on this device.

Runs at hub start, before anything opens the databases. Safe to run again: a record that already has a ULID
keeps it, so a second run finds nothing to do. Before changing anything it copies every database to
backups/pre-ulid-<time>/ (with the old -> new ID map once done); if anything fails, the copies are put back
and the hub doesn't start, so the data is never left half moved.

New IDs carry each record's own creation time, so history stays in order. Notes in the Library keep their own
`uid` (D9), and text that merely mentions an old ID (note provenance, dashboard events) is left as it is.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import time
from pathlib import Path

from .changelog import ChangeLog
from .ids import Generator, is_id, ulid

log = logging.getLogger("sage_os.sync")

OLD_TOKEN = re.compile(r"\b(?:cs|ch|p|dg)_[0-9a-f]{10}\b")      # IDs made before 0.16
DATABASES = ("hub.db", "bookshelf.db", "digest.db", "briefings.db")

# records named by a text ID: (database, table, prefix, time column)
TEXT_IDS = (("hub.db", "claude_sessions", "cs_", "created"), ("hub.db", "chat_sessions", "ch_", "created"),
            ("bookshelf.db", "proposals", "p_", "created"), ("digest.db", "jobs", "dg_", "created"))
# records named by a counting number: (database, table, prefix, time column)
NUMBER_IDS = (("hub.db", "chat_items", "ci_", "ts"), ("bookshelf.db", "batches", "b_", "started"),
              ("briefings.db", "briefings", "br_", "ts"))

# tables rebuilt with a TEXT primary key: their schema after the move
REBUILT = {
    "chat_items": ["CREATE TABLE chat_items (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, ts REAL NOT NULL, "
                   "kind TEXT NOT NULL, data TEXT NOT NULL)",
                   "CREATE INDEX chat_items_session ON chat_items (session_id, id)"],
    "batches": ["CREATE TABLE batches(id TEXT PRIMARY KEY, proposal_id TEXT, agent TEXT, summary TEXT, "
                "status TEXT NOT NULL, started REAL, finished REAL, undone REAL)"],
    "entries": ["CREATE TABLE entries(batch_id TEXT, seq INTEGER, path TEXT NOT NULL, before BLOB, after BLOB, "
                "PRIMARY KEY(batch_id, seq))"],
    "briefings": ["CREATE TABLE briefings(id TEXT PRIMARY KEY, chat TEXT NOT NULL, ts REAL NOT NULL, agent TEXT, "
                  "session TEXT, query TEXT NOT NULL, terms TEXT NOT NULL, items TEXT NOT NULL, deleted REAL)",
                  "CREATE INDEX briefings_chat ON briefings(chat, id)"],
}


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _cols(con: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    return [(r[1], r[2].upper()) for r in con.execute(f"PRAGMA table_info({table})")]


def _only(con: sqlite3.Connection, table: str, cols: tuple[str, ...]) -> None:
    """A rebuilt table must have exactly the columns we copy, or a column would be lost."""
    extra = [c for c, _ in _cols(con, table) if c not in cols]
    if extra:
        raise RuntimeError(f"{table} has columns this migration doesn't know: {extra}")


def _needs(cons: dict[str, sqlite3.Connection]) -> bool:
    for db, table, prefix, _ in TEXT_IDS:
        con = cons.get(db)
        if con and table in _tables(con):
            if any(not is_id(r[0], prefix) for r in con.execute(f"SELECT id FROM {table}")):
                return True
    for db, table, _, _ in NUMBER_IDS:
        con = cons.get(db)
        if con and table in _tables(con) and dict(_cols(con, table)).get("id") == "INTEGER":
            return True
    return False


def run(paths: dict[str, Path], backups: Path, device_id: str) -> dict | None:
    """paths: {"hub.db": ..., "bookshelf.db": ..., ...} (missing files are skipped). -> a report, or None when
    there was nothing to move."""
    paths = {k: Path(v) for k, v in paths.items() if k in DATABASES and Path(v).exists()}
    cons = {k: sqlite3.connect(p) for k, p in paths.items()}
    try:
        if not _needs(cons):
            return None
    finally:
        for c in cons.values():
            c.close()

    folder = backups / f"pre-ulid-{time.strftime('%Y%m%d-%H%M%S')}-{ulid()[-6:]}"
    folder.mkdir(parents=True, exist_ok=False)
    for name, path in paths.items():                  # the backup API copies WAL contents too
        src, dst = sqlite3.connect(path), sqlite3.connect(folder / name)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    log.warning("Y1: moving records to ULIDs; databases backed up to %s", folder)

    cons = {k: sqlite3.connect(p, isolation_level=None) for k, p in paths.items()}
    try:
        maps = _maps(cons)
        for name, con in cons.items():
            con.execute("BEGIN IMMEDIATE")
        _rewrite(cons, maps)
        for name, con in cons.items():
            con.execute("COMMIT")
        seeded = {}
        for name, con in cons.items():
            con.isolation_level = ""                      # back to the default: ChangeLog commits itself
            seeded[name] = ChangeLog(con, name, device_id, missing_ok=True).seed()
    except Exception:
        for con in cons.values():
            try:
                con.close()
            except sqlite3.Error:
                pass
        for name, path in paths.items():
            for extra in (path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
                extra.unlink(missing_ok=True)
            shutil.copy2(folder / name, path)
        log.exception("Y1: moving to ULIDs failed; the databases were put back from %s", folder)
        raise
    for con in cons.values():
        con.close()

    report = {"backup": str(folder), "when": time.time(), "device": device_id,
              "changed": {k: len(v) for k, v in maps.items()}, "logged": seeded}
    (folder / "id-map.json").write_text(json.dumps({"report": report, "map": maps}, indent=1), encoding="utf-8")
    log.warning("Y1: moved to ULIDs: %s", report["changed"])
    return report


def _maps(cons: dict[str, sqlite3.Connection]) -> dict[str, dict]:
    """Old ID -> new ULID per table, each in the order the records were made."""
    maps: dict[str, dict] = {}
    for db, table, prefix, when in TEXT_IDS + NUMBER_IDS:
        con = cons.get(db)
        if not con or table not in _tables(con):
            continue
        rows = con.execute(f"SELECT id, {when} FROM {table}").fetchall()
        gen, m = Generator(), {}
        for old, t in sorted(rows, key=lambda r: (r[1] or 0, r[0])):    # one table's IDs are all text or all numbers
            if isinstance(old, str) and is_id(old, prefix):
                continue
            m[str(old)] = prefix + gen(now_ms=int((t or 0) * 1000))
        maps[table] = m
    return maps


def _rewrite(cons: dict[str, sqlite3.Connection], maps: dict[str, dict]) -> None:
    tokens = {**maps.get("claude_sessions", {}), **maps.get("chat_sessions", {}),
              **maps.get("proposals", {}), **maps.get("jobs", {})}

    def sub(text):
        """Old IDs inside a name ("claude:cs_…") or a JSON list, swapped for the new ones."""
        if not isinstance(text, str):
            return text
        return OLD_TOKEN.sub(lambda m: tokens.get(m.group(0), m.group(0)), text)

    def remap(con, table, column, mapping):
        for old, new in mapping.items():
            con.execute(f"UPDATE {table} SET {column}=? WHERE {column}=?", (new, old))

    def rebuild(con, table, rows):
        con.execute(f"DROP TABLE {table}")
        for sql in REBUILT[table]:
            con.execute(sql)
        if rows:
            con.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(rows[0]))})", rows)

    if con := cons.get("hub.db"):
        have = _tables(con)
        for table in ("claude_sessions", "chat_sessions"):
            if table in have:
                remap(con, table, "id", maps.get(table, {}))
        if "chat_items" in have:
            _only(con, "chat_items", ("id", "session_id", "ts", "kind", "data"))
            m = maps.get("chat_items", {})
            rows = [(m.get(str(i), i), sub(s), ts, k, d) for i, s, ts, k, d in
                    con.execute("SELECT id, session_id, ts, kind, data FROM chat_items").fetchall()]
            rebuild(con, "chat_items", rows)

    if con := cons.get("bookshelf.db"):
        have = _tables(con)
        bm = maps.get("batches", {})
        if "proposals" in have:
            remap(con, "proposals", "id", maps.get("proposals", {}))
            for pid, agent, batch in con.execute("SELECT id, agent, batch_id FROM proposals").fetchall():
                con.execute("UPDATE proposals SET agent=?, batch_id=? WHERE id=?",
                            (sub(agent), bm.get(str(batch), batch) if batch is not None else None, pid))
        if "batches" in have:
            _only(con, "batches", ("id", "proposal_id", "agent", "summary", "status", "started", "finished", "undone"))
            rows = [(bm.get(str(i), i), tokens.get(p, p), sub(a), *rest) for i, p, a, *rest in con.execute(
                "SELECT id, proposal_id, agent, summary, status, started, finished, undone FROM batches").fetchall()]
            rebuild(con, "batches", rows)
        if "entries" in have:
            _only(con, "entries", ("batch_id", "seq", "path", "before", "after"))
            rows = [(bm.get(str(b), b), *rest) for b, *rest in
                    con.execute("SELECT batch_id, seq, path, before, after FROM entries").fetchall()]
            rebuild(con, "entries", rows)

    if con := cons.get("digest.db"):
        have = _tables(con)
        jm = maps.get("jobs", {})
        if "jobs" in have:
            remap(con, "jobs", "id", jm)
        for table in ("secs", "chapters"):
            if table in have:
                remap(con, table, "job", jm)
        if "chapters" in have:
            for job, chapter, props in con.execute("SELECT job, chapter, proposals FROM chapters").fetchall():
                if props:
                    con.execute("UPDATE chapters SET proposals=? WHERE job=? AND chapter=?", (sub(props), job, chapter))

    if con := cons.get("briefings.db"):
        have = _tables(con)
        if "briefings" in have:
            _only(con, "briefings", ("id", "chat", "ts", "agent", "session", "query", "terms", "items", "deleted"))
            m = maps.get("briefings", {})
            deleted = "deleted" if "deleted" in dict(_cols(con, "briefings")) else "NULL"
            rows = []
            for r in con.execute(f"SELECT id, chat, ts, agent, session, query, terms, items, {deleted} FROM briefings").fetchall():
                i, chat, ts, agent, session, *rest = r
                rows.append((m.get(str(i), i), sub(chat), ts, sub(agent), sub(session), *rest))
            rebuild(con, "briefings", rows)
        if "briefing_chats" in have:
            for (chat,) in con.execute("SELECT chat FROM briefing_chats").fetchall():
                if sub(chat) != chat:
                    con.execute("UPDATE briefing_chats SET chat=? WHERE chat=?", (sub(chat), chat))
