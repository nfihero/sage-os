"""The single writer (K3): the only code that changes the vault, and only for an approved proposal.

BookShelf invariants, carried into Python (DECISIONS D2, D11, D12):
  I4  screened content never stored -- `propose` screens everything the proposer sent before the
      journal sees it (screen.py); a hit refuses the whole proposal.
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

from .proposals import Entry, ProposalError, apply_review, normalize, plan, screen_proposal, sha
from .vault import ARCHIVE, Vault
from ..sync import new_id


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
          CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, proposal_id TEXT, agent TEXT, summary TEXT,
            status TEXT NOT NULL, started REAL, finished REAL, undone REAL);
          CREATE TABLE IF NOT EXISTS entries(batch_id TEXT, seq INTEGER, path TEXT NOT NULL,
            before BLOB, after BLOB, PRIMARY KEY(batch_id, seq));
        """)
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(proposals)")]
        if "screened" not in cols:
            # K4 override: the screening category the user chose to save anyway (never the content)
            self.db.execute("ALTER TABLE proposals ADD COLUMN screened TEXT")
        if "original" not in cols:      # review (K13): the proposal as the agent sent it, and what the user kept/edited
            self.db.execute("ALTER TABLE proposals ADD COLUMN original TEXT")
            self.db.execute("ALTER TABLE proposals ADD COLUMN review TEXT")
        if "grp" not in cols:           # K7: the parts of one chapter (or run) share a group, decided as one card
            self.db.execute("ALTER TABLE proposals ADD COLUMN grp TEXT")
            self.db.execute("ALTER TABLE proposals ADD COLUMN grp_title TEXT")
            self.db.execute("ALTER TABLE proposals ADD COLUMN auto TEXT")       # the trust level that filed it, if any
            self.db.execute("ALTER TABLE proposals ADD COLUMN verdict TEXT")    # the reviewer's pre-marks (JSON)
        if "proposal_ids" not in [r[1] for r in self.db.execute("PRAGMA table_info(batches)")]:
            self.db.execute("ALTER TABLE batches ADD COLUMN proposal_ids TEXT")  # every proposal a decision filed
        if "undone" not in [r[1] for r in self.db.execute("PRAGMA table_info(entries)")]:
            self.db.execute("ALTER TABLE entries ADD COLUMN undone REAL")         # one note undone from a batch
        self.db.commit()

    # -- proposals -----------------------------------------------------------------------------
    def propose(self, agent: str, summary: str, changes: list, *, override: str | None = None,
                group: str | None = None, group_title: str | None = None) -> dict:
        """Check and store a proposal; the vault is not touched. -> proposal with a preview per change.

        `override` is the user's "Save anyway" (K4): the screening category they accepted. Only the
        inbox's held-proposal resolver passes it; agents can't. `group` ties the parts of one chapter or run
        together (K7); only Sage OS's own jobs set it.
        """
        agent, summary, norm = self._check(agent, summary, changes)
        if override is None:
            screen_proposal(agent, summary, norm)      # K4: before anything is stored (I4)
        with self.lock:
            planned = plan(self.vault, norm, agent)
            bases = {e.path: sha(e.before) for p in planned for e in p.entries if e.before is not None}
            pid = new_id("p_")
            self.db.execute("INSERT INTO proposals(id, agent, summary, created, status, changes, bases, screened, grp, grp_title) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (pid, agent, summary, time.time(), "pending", json.dumps(norm), json.dumps(bases), override,
                             group, (group_title or "")[:300] or None))
            self.db.commit()
        return self.proposal(pid) | {"preview": [p.preview() for p in planned]}

    @_locked
    def set_group(self, pid: str, group: str, title: str | None) -> None:
        self.db.execute("UPDATE proposals SET grp=?, grp_title=? WHERE id=? AND grp IS NULL", (group, title, pid))
        self.db.commit()

    @_locked
    def set_verdict(self, pid: str, verdict: dict | None) -> None:
        self.db.execute("UPDATE proposals SET verdict=? WHERE id=?", (json.dumps(verdict) if verdict else None, pid))
        self.db.commit()

    @_locked
    def group_pending(self, group: str) -> bool:
        """A part of this chapter (or run) already waits: a later part joins its card instead of adding one."""
        return self.db.execute("SELECT 1 FROM proposals WHERE status='pending' AND grp=? LIMIT 1", (group,)).fetchone() is not None

    @_locked
    def pending_groups(self, agent: str) -> int:
        """How many inbox cards this agent's waiting proposals make (a chapter's parts are one card)."""
        return self.db.execute("SELECT COUNT(DISTINCT COALESCE(grp, id)) FROM proposals WHERE status='pending' AND agent=?",
                               (agent,)).fetchone()[0]

    @staticmethod
    def _check(agent, summary, changes) -> tuple[str, str, list[dict]]:
        if not isinstance(agent, str) or not agent.strip() or len(agent) > 200 or "\n" in agent:
            raise ProposalError("agent must name who is proposing, e.g. claude:<session> or hermes:default:<session>")
        return agent.strip(), (summary or "").strip()[:500], normalize(changes)

    def render(self, agent: str, summary: str, changes: list) -> list[dict]:
        """Preview a proposal without screening or storing it (for a held card, kept in memory only)."""
        agent, _, norm = self._check(agent, summary, changes)
        with self.lock:
            return [p.preview() for p in plan(self.vault, norm, agent)]

    @_locked
    def proposal(self, pid: str) -> dict | None:
        keys = ("id", "agent", "summary", "created", "status", "decided", "note", "changes", "batch_id", "screened",
                "grp", "grp_title", "auto", "verdict", "review")
        row = self.db.execute(f"SELECT {', '.join(keys)} FROM proposals WHERE id=?", (pid,)).fetchone()
        if row is None:
            return None
        p = dict(zip(keys, row))
        p["changes"] = json.loads(p["changes"])
        p["verdict"] = json.loads(p["verdict"]) if p["verdict"] else None
        p["review"] = json.loads(p["review"]) if p["review"] else None
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

    def _decide(self, pid, status, note, batch_id=None, auto=None):
        p = self.proposal(pid)
        if p is None or p["status"] != "pending":
            raise ProposalError(f"proposal {pid} is not pending")
        self.db.execute("UPDATE proposals SET status=?, decided=?, note=?, batch_id=?, auto=? WHERE id=?",
                        (status, time.time(), note or None, batch_id, auto, pid))
        self.db.commit()

    # -- applying --------------------------------------------------------------------------------
    def approve(self, pid: str, note: str = "", review: dict | None = None, *, auto: str | None = None) -> dict:
        """Apply an approved proposal as one batch. Only the inbox's resolver, or the trust level the user gave
        the agent (K7, D36), calls this (I1).

        `review` is the user's keep/edit pass ({"keep": [indexes], "edits": {index: {title, body, tags}}}): only
        kept changes are filed, edited ones as edited. The proposal as sent is kept in `original`."""
        return self.approve_many([pid], note, {pid: review} if review is not None else None, auto=auto)

    def approve_many(self, pids: list[str], note: str = "", reviews: dict | None = None, *,
                     auto: str | None = None) -> dict:
        """File several proposals as ONE batch (K7): one decision, one undo, all filed or none (I9).

        `reviews` maps a proposal id to its keep/edit pass; a part whose notes were all dropped is rejected
        and the rest filed. -> the batch."""
        reviews = reviews or {}
        if not pids or len(set(pids)) != len(pids):
            raise ProposalError("choose at least one proposal, each once")
        with self.lock:
            props = []
            for pid in pids:
                p = self.proposal(pid)
                if p is None or p["status"] != "pending":
                    raise ProposalError(f"proposal {pid} is not pending")
                props.append(p)
            notes, taken, seen = self.vault.scan(), set(), set()
            entries: list[Entry] = []
            filed, dropped = [], []
            for p in props:
                reviewed = None
                review = reviews.get(p["id"])
                if review is not None:
                    changes, summary = apply_review(p["changes"], review.get("keep"), review.get("edits"))
                    if not changes:
                        if len(props) == 1:
                            raise ProposalError("nothing kept: reject the proposal instead")
                        dropped.append(p)
                        continue
                    screen_proposal(p["agent"], p["summary"] or "", [c for c in changes if c.get("edited_by")])  # K4 on edits
                    reviewed = (changes, summary)
                    p["changes"] = changes        # recorded on the proposal only once it has been filed
                uids = {c["uid"] for c in p["changes"] if c["op"] != "create"}
                if uids & seen:
                    raise ProposalError("two of these proposals change the same note; decide them one at a time")
                seen |= uids
                bases = json.loads(self.db.execute("SELECT bases FROM proposals WHERE id=?", (p["id"],)).fetchone()[0])
                entries += [e for x in plan(self.vault, p["changes"], p["agent"], bases, notes=notes, taken=taken)
                            for e in x.entries]
                filed.append((p, reviewed))
            if not filed:
                raise ProposalError("nothing kept: reject these instead")
            first = filed[0][0]
            agents = {p["agent"] for p, _ in filed}
            groups = {p["grp"] for p, _ in filed}
            if len(filed) == 1:
                summary = first["summary"]
            elif len(groups) == 1 and first["grp"]:
                summary = f"{first['grp_title'] or first['summary']} ({len(filed)} parts)"
            else:
                summary = f"{len(filed)} proposals filed together"
            batch = self._journal([p["id"] for p, _ in filed], first["agent"] if len(agents) == 1 else "several agents",
                                  summary, entries)
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
            for p, reviewed in filed:
                if reviewed:                      # the agent's version stays in `original`
                    self.db.execute("UPDATE proposals SET original=COALESCE(original, changes), changes=?, review=? WHERE id=?",
                                    (json.dumps(reviewed[0]), json.dumps(reviewed[1]), p["id"]))
                self._decide(p["id"], "applied", note, batch, auto)
            for p in dropped:
                self._decide(p["id"], "rejected", note or "every note was dropped in review")
        return self.batch(batch)

    def _journal(self, pids, agent, summary, entries) -> str:
        """Write-ahead: the batch and every before/after is on disk before any note changes."""
        bid = new_id("b_")
        self.db.execute("INSERT INTO batches(id, proposal_id, agent, summary, status, started, proposal_ids) VALUES (?,?,?,?,?,?,?)",
                        (bid, pids[0], agent, summary, "applying", time.time(), json.dumps(pids)))
        self.db.executemany("INSERT INTO entries(batch_id, seq, path, before, after) VALUES (?,?,?,?,?)",
                            [(bid, i, e.path, e.before, e.after) for i, e in enumerate(entries)])
        self.db.commit()
        return bid

    def _finish(self, batch: str, status: str):
        col = "undone" if status == "undone" else "finished"
        self.db.execute(f"UPDATE batches SET status=?, {col}=? WHERE id=?", (status, time.time(), batch))
        self.db.commit()

    @_locked
    def _entries(self, batch: str, include_undone: bool = True) -> list[Entry]:
        return [Entry(p, b, a) for p, b, a in self.db.execute(
            "SELECT path, before, after FROM entries WHERE batch_id=?" + ("" if include_undone else " AND undone IS NULL")
            + " ORDER BY seq", (batch,))]

    def undo(self, batch: str) -> dict:
        """Put every file of the batch back exactly as it was. Refuses if any was edited since. Notes already
        undone one by one (K7) stay as they are."""
        with self.lock:
            b = self.batch(batch)
            if b is None or b["status"] != "applied":
                raise ProposalError(f"batch {batch} can't be undone (it is {b['status'] if b else 'unknown'})")
            entries = self._entries(batch, include_undone=False)
            changed = [e.path for e in entries if _current(self.vault.root / e.path) != e.after]
            if changed:
                raise ProposalError(f"changed since this batch was applied, so undo would overwrite edits: {', '.join(changed)}")
            self.db.execute("UPDATE batches SET status='undoing' WHERE id=?", (batch,))
            self.db.commit()
            for e in reversed(entries):
                _put(self.vault.root / e.path, e.before)
            self._finish(batch, "undone")
        return self.batch(batch)

    def undo_note(self, batch: str, seq: int) -> dict:
        """Undo one note of a filed batch (K7): its file goes back exactly as it was; the rest stay filed. An
        archived note's two halves (the copy under Archive/ and the removed original) go back together.
        -> {"batch", "paths"}"""
        with self.lock:
            b = self.batch(batch)
            if b is None or b["status"] != "applied":
                raise ProposalError(f"batch {batch} can't be changed (it is {b['status'] if b else 'unknown'})")
            rows = {s: (Entry(p, bf, af), u) for s, p, bf, af, u in self.db.execute(
                "SELECT seq, path, before, after, undone FROM entries WHERE batch_id=?", (batch,))}
            if seq not in rows:
                raise ProposalError("no such note in this batch")
            if rows[seq][1] is not None:
                raise ProposalError("that note was already undone")
            e = rows[seq][0]
            if e.path.startswith(f"{ARCHIVE}/") and e.before is None:
                pair = e.path[len(ARCHIVE) + 1:]
            elif e.after is None:
                pair = f"{ARCHIVE}/{e.path}"
            else:
                pair = None
            seqs = [seq] + [s for s, (o, u) in rows.items() if pair and s != seq and o.path == pair and u is None]
            entries = [rows[s][0] for s in seqs]
            changed = [x.path for x in entries if _current(self.vault.root / x.path) != x.after]
            if changed:
                raise ProposalError(f"changed since it was filed, so undo would overwrite edits: {', '.join(changed)}")
            for x in entries:
                _put(self.vault.root / x.path, x.before)
            now = time.time()
            self.db.executemany("UPDATE entries SET undone=? WHERE batch_id=? AND seq=?", [(now, batch, s) for s in seqs])
            self.db.commit()
            if not self.db.execute("SELECT 1 FROM entries WHERE batch_id=? AND undone IS NULL", (batch,)).fetchone():
                self._finish(batch, "undone")
        return {"batch": self.batch(batch), "paths": [x.path for x in entries]}

    def recover(self) -> list[str]:
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
    def batch(self, batch: str) -> dict | None:
        keys = ("id", "proposal_id", "agent", "summary", "status", "started", "finished", "undone", "proposal_ids")
        row = self.db.execute(f"SELECT {', '.join(keys)} FROM batches WHERE id=?", (batch,)).fetchone()
        if row is None:
            return None
        b = dict(zip(keys, row))
        b["proposal_ids"] = json.loads(b["proposal_ids"]) if b["proposal_ids"] else [b["proposal_id"]]
        auto = self.db.execute("SELECT auto FROM proposals WHERE id=?", (b["proposal_id"],)).fetchone()
        b["auto"] = auto[0] if auto else None         # filed by the agent's trust level, not a decision of the user's
        b["files"] = [{"seq": seq, "path": path, "op": "create" if no_before else "remove" if no_after else "update",
                       "undone": undone}
                      for seq, path, no_before, no_after, undone in self.db.execute(
                          "SELECT seq, path, before IS NULL, after IS NULL, undone FROM entries WHERE batch_id=? ORDER BY seq",
                          (batch,))]
        return b

    @_locked
    def auto_batches(self, limit: int = 20) -> list[dict]:
        """What agents filed by themselves (their trust level), newest first: the inbox's *Filed for you*."""
        rows = self.db.execute("SELECT DISTINCT batch_id FROM proposals WHERE auto IS NOT NULL AND batch_id IS NOT NULL "
                               "ORDER BY decided DESC LIMIT ?", (limit,)).fetchall()
        return [self.batch(r[0]) for r in rows]

    @_locked
    def history(self, limit: int = 100) -> list[dict]:
        return [self.batch(r[0]) for r in self.db.execute("SELECT id FROM batches ORDER BY id DESC LIMIT ?", (limit,))]

    def close(self):
        with self.lock:
            self.db.close()
