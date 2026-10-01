"""Bookshelf search (K2): a SQLite FTS5 index over the vault.

The index is a cache (BookShelf I3): it lives outside the vault, holds nothing the notes don't, and
can be deleted at any time -- `rebuild` recreates it from the files. `sync` keeps it current by
re-reading only notes whose size or mtime changed.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from .vault import Note

SCHEMA = 1                      # bump to drop and rebuild old indexes
HIT_START, HIT_END = "\x02", "\x03"   # snippet markers; the UI turns them into highlights
WEIGHTS = (10.0, 5.0, 1.0)      # bm25 weights: title, tags, body
TERM = re.compile(r"\w+", re.UNICODE)


def fts_query(text: str) -> str | None:
    """User text -> a safe FTS5 query. Every word must match, whole (stemmed) or as a prefix."""
    terms = TERM.findall(text.lower())[:12]
    if not terms:
        return None
    # Porter stems indexed words, but prefix queries aren't stemmed: "valuation*" can't match the
    # stored "valuat". Asking for the word itself (stemmed) OR the prefix covers both.
    return " AND ".join(f'("{t}" OR "{t}"*)' for t in terms)


class SearchIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.synced_at: float | None = None
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self._setup()

    def _setup(self):
        with self._lock:
            c = self.con
            c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
            row = c.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if row and row[0] != str(SCHEMA):
                c.executescript("DROP TABLE IF EXISTS docs; DROP TABLE IF EXISTS fts;")
            c.executescript("""
              CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, ref TEXT,
                title TEXT, folder TEXT, archived INTEGER, mtime REAL, size INTEGER);
              CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, tags, body,
                tokenize='porter unicode61 remove_diacritics 2');
            """)
            c.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(SCHEMA),))
            c.commit()

    def count(self) -> int:
        with self._lock:
            return self.con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]

    def sync(self, notes: Iterable[Note], read_body: Callable[[str], str | None]) -> dict:
        """Bring the index in line with the vault. -> {"added", "updated", "removed", "ms"}."""
        t0 = time.perf_counter()
        added = updated = 0
        with self._lock:
            c = self.con
            have = {p: (i, m, s, r) for i, p, m, s, r in c.execute("SELECT id, path, mtime, size, ref FROM docs")}
            seen = set()
            for n in notes:
                seen.add(n.path)
                old = have.get(n.path)
                if old and old[1] == n.mtime and old[2] == n.size:
                    if old[3] != n.ref:            # e.g. a duplicate uid elsewhere changed this note's ref
                        c.execute("UPDATE docs SET ref=? WHERE id=?", (n.ref, old[0]))
                    continue
                body = read_body(n.path)
                if body is None:                   # vanished or unreadable since the scan
                    continue
                row = (n.ref, n.title, n.folder, int(n.archived), n.mtime, n.size)
                if old:
                    c.execute("UPDATE docs SET ref=?, title=?, folder=?, archived=?, mtime=?, size=? WHERE id=?", (*row, old[0]))
                    c.execute("DELETE FROM fts WHERE rowid=?", (old[0],))
                    doc_id, updated = old[0], updated + 1
                else:
                    doc_id = c.execute("INSERT INTO docs(path, ref, title, folder, archived, mtime, size) VALUES (?,?,?,?,?,?,?)",
                                       (n.path, *row)).lastrowid
                    added += 1
                c.execute("INSERT INTO fts(rowid, title, tags, body) VALUES (?,?,?,?)",
                          (doc_id, n.title, " ".join(n.tags), body))
            gone = [(have[p][0],) for p in set(have) - seen]
            c.executemany("DELETE FROM fts WHERE rowid=?", gone)
            c.executemany("DELETE FROM docs WHERE id=?", gone)
            c.commit()
        self.synced_at = time.time()
        return {"added": added, "updated": updated, "removed": len(gone), "ms": round((time.perf_counter() - t0) * 1000, 1)}

    def rebuild(self, notes: Iterable[Note], read_body: Callable[[str], str | None]) -> dict:
        """Drop everything and index the vault from cold."""
        with self._lock:
            self.con.executescript("DELETE FROM fts; DELETE FROM docs;")
            self.con.commit()
        return self.sync(notes, read_body)

    def search(self, text: str, *, limit: int = 30, archived: bool = False) -> dict:
        """-> {"q", "ms", "results": [{path, ref, title, folder, archived, snippet, score}]}, best first."""
        t0 = time.perf_counter()
        q = fts_query(text)
        rows = []
        if q:
            with self._lock:
                rows = self.con.execute(f"""
                  SELECT d.path, d.ref, d.title, d.folder, d.archived,
                         snippet(fts, -1, ?, ?, '…', 14), bm25(fts, {', '.join(map(str, WEIGHTS))})
                  FROM fts JOIN docs d ON d.id = fts.rowid
                  WHERE fts MATCH ? AND (? OR d.archived = 0)
                  ORDER BY 7 LIMIT ?""", (HIT_START, HIT_END, q, int(archived), limit)).fetchall()
        results = [{"path": p, "ref": r, "title": t, "folder": f, "archived": bool(a), "snippet": s, "score": round(-sc, 3)}
                   for p, r, t, f, a, s, sc in rows]
        return {"q": text, "ms": round((time.perf_counter() - t0) * 1000, 1), "results": results}

    def close(self):
        with self._lock:
            self.con.close()
