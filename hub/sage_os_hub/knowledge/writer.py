"""The single writer (K3): the only code that changes the vault, and only for an approved proposal.

BookShelf invariants, carried into Python (DECISIONS D2, D11):
  I1  no write without approval -- `approve` is called only from the inbox's resolver; no HTTP route
      reaches it directly, and agents (K5) get propose tools only.
  I2  every write journaled and reversible -- the journal keeps exact before/after bytes per file;
      `undo` restores them byte for byte, per batch.
  I9  fully filed or untouched -- everything is planned and checked first, the journal is written
      ahead of the files, a failure rolls back what was done, and `recover` finishes the job after a
      crash.
One lock serializes all writes, so concurrent approvals can't race (BookShelf's P5).
"""
from __future__ import annotations

import functools
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .proposals import Entry, ProposalError, normalize, plan, sha
from .vault import Vault


def _locked(fn):
    """Reads share the writer's SQLite connection across threads, so they take the lock too."""
    @functools.wraps(fn)
    def wrap(self, *args, **kw):
        with self.lock:
            return fn(self, *args, **kw)
    return wrap


def _current(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _put(path: Path, data: bytes | None) -> None:
    """Make the file hold exactly `data` (None = no file). Temp file + atomic rename."""
    if data is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:6]}.tmp")   # dot-prefixed: the scanner skips it
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Writer:
    def __init__(self, vault: Vault, journal_path: Path):
        self.vault = vault
        Path(journal_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(journal_path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, agent TEXT NOT NULL, summary TEXT,
            created REAL, status TEXT NOT NULL, decided REAL, note TEXT, changes TEXT NOT NULL,
            bases TEXT NOT NULL, batch_id INTEGER);
          CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY, proposal_id TEXT, agent TEXT, summary TEXT,
            status TEXT NOT NULL, started REAL, finished REAL, undone REAL);
          CREATE TABLE IF NOT EXISTS entries(batch_id INTEGER, seq INTEGER, path TEXT NOT NULL,
            before BLOB, after BLOB, PRIMARY KEY(batch_id, seq));
        """)

    # -- proposals -----------------------------------------------------------------------------
    def propose(self, agent: str, summary: str, changes: list) -> dict:
        """Check and store a proposal; the vault is not touched. -> proposal with a preview per change."""
        if not isinstance(agent, str) or not agent.strip() or len(agent) > 200 or "\n" in agent:
            raise ProposalError("agent must name who is proposing, e.g. claude:<session> or hermes:default:<session>")
        summary = (summary or "").strip()[:500]
        norm = normalize(changes)
        with self.lock:
            planned = plan(self.vault, norm, agent.strip())
            bases = {e.path: sha(e.before) for p in planned for e in p.entries if e.before is not None}
            pid = f"p_{uuid.uuid4().hex[:10]}"
            self.db.execute("INSERT INTO proposals(id, agent, summary, created, status, changes, bases) VALUES (?,?,?,?,?,?,?)",
                            (pid, agent.strip(), summary, time.time(), "pending", json.dumps(norm), json.dumps(bases)))
            self.db.commit()
        return self.proposal(pid) | {"preview": [p.preview() for p in planned]}

    @_locked
    def proposal(self, pid: str) -> dict | None:
        row = self.db.execute("SELECT id, agent, summary, created, status, decided, note, changes, batch_id FROM proposals WHERE id=?",
                              (pid,)).fetchone()
        if row is None:
            return None
        keys = ("id", "agent", "summary", "created", "status", "decided", "note", "changes", "batch_id")
        p = dict(zip(keys, row))
        p["changes"] = json.loads(p["changes"])
        return p

    @_locked
    def proposals(self, status: str | None = None, limit: int = 100) -> list[dict]:
        q = "SELECT id FROM proposals" + (" WHERE status=?" if status else "") + " ORDER BY created DESC LIMIT ?"
        return [self.proposal(r[0]) for r in self.db.execute(q, ((status, limit) if status else (limit,)))]

    @_locked
    def preview(self, pid: str) -> list[dict]:
        """Re-render a pending proposal against the vault as it is now (for the inbox card)."""
        p = self.proposal(pid)
        bases = json.loads(self.db.execute("SELECT bases FROM proposals WHERE id=?", (pid,)).fetchone()[0])
        return [x.preview() for x in plan(self.vault, p["changes"], p["agent"], bases)]

    def reject(self, pid: str, note: str = "") -> dict:
        with self.lock:
            self._decide(pid, "rejected", note)
        return self.proposal(pid)

    def _decide(self, pid, status, note, batch_id=None):
        p = self.proposal(pid)
        if p is None or p["status"] != "pending":
            raise ProposalError(f"proposal {pid} is not pending")
        self.db.execute("UPDATE proposals SET status=?, decided=?, note=?, batch_id=? WHERE id=?",
                        (status, time.time(), note or None, batch_id, pid))
        self.db.commit()

    # -- applying --------------------------------------------------------------------------------
    def approve(self, pid: str, note: str = "") -> dict:
        """Apply an approved proposal as one batch. Only the inbox's resolver calls this (I1)."""
        with self.lock:
            p = self.proposal(pid)
            if p is None or p["status"] != "pending":
                raise ProposalError(f"proposal {pid} is not pending")
            bases = json.loads(self.db.execute("SELECT bases FROM proposals WHERE id=?", (pid,)).fetchone()[0])
            entries = [e for x in plan(self.vault, p["changes"], p["agent"], bases) for e in x.entries]
            batch = self._journal(pid, p["agent"], p["summary"], entries)
            done: list[Entry] = []
            try:
                for e in entries:
                    _put(self.vault.root / e.path, e.after)
                    done.append(e)
            except OSError as exc:
                for e in reversed(done):
                    _put(self.vault.root / e.path, e.before)
                self._finish(batch, "rolled_back")
                raise ProposalError(f"writing {len(done) + 1} of {len(entries)} failed ({exc}); nothing was changed") from exc
            self._finish(batch, "applied")
            self._decide(pid, "applied", note, batch)
        return self.batch(batch)

    def _journal(self, pid, agent, summary, entries) -> int:
        """Write-ahead: the batch and every before/after is on disk before any note changes."""
        cur = self.db.execute("INSERT INTO batches(proposal_id, agent, summary, status, started) VALUES (?,?,?,?,?)",
                              (pid, agent, summary, "applying", time.time()))
        self.db.executemany("INSERT INTO entries VALUES (?,?,?,?,?)",
                            [(cur.lastrowid, i, e.path, e.before, e.after) for i, e in enumerate(entries)])
        self.db.commit()
        return cur.lastrowid

    def _finish(self, batch: int, status: str):
        col = "undone" if status == "undone" else "finished"
        self.db.execute(f"UPDATE batches SET status=?, {col}=? WHERE id=?", (status, time.time(), batch))
        self.db.commit()

    @_locked
    def _entries(self, batch: int) -> list[Entry]:
        return [Entry(p, b, a) for p, b, a in self.db.execute(
            "SELECT path, before, after FROM entries WHERE batch_id=? ORDER BY seq", (batch,))]

    def undo(self, batch: int) -> dict:
        """Put every file of the batch back exactly as it was. Refuses if any was edited since."""
        with self.lock:
            b = self.batch(batch)
            if b is None or b["status"] != "applied":
                raise ProposalError(f"batch {batch} can't be undone (it is {b['status'] if b else 'unknown'})")
            entries = self._entries(batch)
            changed = [e.path for e in entries if _current(self.vault.root / e.path) != e.after]
            if changed:
                raise ProposalError(f"changed since this batch was applied, so undo would overwrite edits: {', '.join(changed)}")
            self.db.execute("UPDATE batches SET status='undoing' WHERE id=?", (batch,))
            self.db.commit()
            for e in reversed(entries):
                _put(self.vault.root / e.path, e.before)
            self._finish(batch, "undone")
        return self.batch(batch)

    def recover(self) -> list[int]:
        """After a crash: batches caught mid-apply or mid-undo are put back to their 'before' state."""
        fixed = []
        with self.lock:
            for (batch, status) in self.db.execute("SELECT id, status FROM batches WHERE status IN ('applying','undoing')").fetchall():
                for e in reversed(self._entries(batch)):
                    cur = _current(self.vault.root / e.path)
                    if cur == e.after or cur is None or cur == e.before:
                        _put(self.vault.root / e.path, e.before)
                self._finish(batch, "rolled_back" if status == "applying" else "undone")
                fixed.append(batch)
        return fixed

    # -- history ---------------------------------------------------------------------------------
    @_locked
    def batch(self, batch: int) -> dict | None:
        row = self.db.execute("SELECT id, proposal_id, agent, summary, status, started, finished, undone FROM batches WHERE id=?",
                              (batch,)).fetchone()
        if row is None:
            return None
        b = dict(zip(("id", "proposal_id", "agent", "summary", "status", "started", "finished", "undone"), row))
        b["files"] = [{"path": e.path, "op": "create" if e.before is None else "remove" if e.after is None else "update"}
                      for e in self._entries(batch)]
        return b

    @_locked
    def history(self, limit: int = 100) -> list[dict]:
        return [self.batch(r[0]) for r in self.db.execute("SELECT id FROM batches ORDER BY id DESC LIMIT ?", (limit,))]

    def close(self):
        with self.lock:
            self.db.close()
