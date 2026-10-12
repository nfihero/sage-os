"""Roles, trust levels and every agent's activity log (K7, D36).

An agent's trust is the user's standing decision about its proposals, on BookShelf's three-step ladder:

  ask        everything it proposes waits in the inbox (the default)
  new_notes  proposals that only add notes are filed at once; changes to existing notes still wait
  trusted    everything it proposes is filed at once

Whatever the level, screening (K4) still holds secret-looking proposals, every filed batch can be undone, and the
activity log records what the agent did: searches, reads, proposals, what was filed and by whom, undos. The log
lives in the Bookshelf journal (bookshelf.db) and syncs like the user's decisions; nothing is ever trimmed.

Agents are named by proposer ids ("claude:<session>", "hermes:<profile>:<session>", "digest:<model>"); trust
and roles belong to the agent, not a session, so they are kept per *key* ("claude", "hermes:<profile>", "digest").
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time

from ..sync import new_id

LEVELS = ("ask", "new_notes", "trusted")
ROLES = ("researcher", "librarian", "reviewer")
SUGGEST_AFTER = 10            # clean approvals in a row before Sage OS suggests the next level
LABELS = {"claude": "Claude Code", "chat": "Model chat", "digest": "Digest", "librarian": "Librarian",
          "reviewer": "Reviewer", "importer": "Starter notes"}
DEFAULT_ROLE = {"librarian": "librarian", "reviewer": "reviewer"}


def agent_key(proposer: str) -> str:
    """The agent behind a proposer id: one key per agent, whatever session or model it ran in."""
    if proposer == "sage-os:importer":
        return "importer"
    parts = proposer.split(":")
    if parts[0] == "hermes" and len(parts) > 1:
        return f"hermes:{parts[1]}"
    return parts[0]


def label(key: str) -> str:
    if key.startswith("hermes:"):
        return f"Hermes ({key.split(':', 1)[1]})"
    return LABELS.get(key, key)


def allows(level: str, changes: list[dict]) -> bool:
    """Whether a proposal of these changes files itself at this trust level."""
    if level == "trusted":
        return True
    return level == "new_notes" and all(c.get("op") == "create" for c in changes)


class Trust:
    """Lives in the Bookshelf journal's database and shares the writer's lock."""

    def __init__(self, db: sqlite3.Connection, lock: threading.RLock):
        self.db, self.lock = db, lock
        with self.lock:
            self.db.executescript("""
              CREATE TABLE IF NOT EXISTS trust(key TEXT PRIMARY KEY, level TEXT NOT NULL DEFAULT 'ask', role TEXT,
                config TEXT, updated REAL, quiet_until INTEGER NOT NULL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS agent_log(id TEXT PRIMARY KEY, ts REAL NOT NULL, agent TEXT NOT NULL,
                key TEXT NOT NULL, action TEXT NOT NULL, detail TEXT, ref TEXT);
              CREATE INDEX IF NOT EXISTS agent_log_key ON agent_log(key, ts);
            """)
            self.db.commit()

    # -- the log ------------------------------------------------------------------------------------------
    def log(self, agent: str, action: str, detail: str = "", ref: dict | None = None, key: str | None = None) -> dict:
        """Record one thing an agent did (or that was done with its work). Never fails the action it records."""
        row = {"id": new_id("al_"), "ts": time.time(), "agent": agent, "key": key or agent_key(agent),
               "action": action, "detail": (detail or "")[:1000], "ref": ref or {}}
        try:
            with self.lock:
                self.db.execute("INSERT INTO agent_log(id, ts, agent, key, action, detail, ref) VALUES (?,?,?,?,?,?,?)",
                                (row["id"], row["ts"], agent, row["key"], action, row["detail"], json.dumps(row["ref"])))
                self.db.commit()
        except sqlite3.Error:
            pass
        return row

    def activity(self, key: str | None = None, limit: int = 200, before: float | None = None) -> list[dict]:
        q, args = "SELECT id, ts, agent, key, action, detail, ref FROM agent_log WHERE 1=1", []
        if key:
            q += " AND key=?"
            args.append(key)
        if before:
            q += " AND ts<?"
            args.append(before)
        q += " ORDER BY ts DESC LIMIT ?"
        args.append(max(1, min(limit, 1000)))
        with self.lock:
            rows = self.db.execute(q, args).fetchall()
        return [{"id": i, "ts": ts, "agent": a, "key": k, "action": ac, "detail": d, "ref": json.loads(r or "{}")}
                for i, ts, a, k, ac, d, r in rows]

    # -- levels and roles ---------------------------------------------------------------------------------
    def get(self, key: str) -> dict:
        with self.lock:
            row = self.db.execute("SELECT level, role, config, quiet_until FROM trust WHERE key=?", (key,)).fetchone()
        level, role, config, quiet = row or ("ask", None, None, 0)
        return {"key": key, "label": label(key), "level": level if level in LEVELS else "ask",
                "role": role or DEFAULT_ROLE.get(key, "researcher"), "config": json.loads(config or "{}"),
                "quiet_until": quiet}

    def level(self, proposer: str) -> str:
        return self.get(agent_key(proposer))["level"]

    def set(self, key: str, *, level: str | None = None, role: str | None = None, config: dict | None = None,
            quiet_until: int | None = None, by: str = "user") -> dict:
        if level is not None and level not in LEVELS:
            raise ValueError(f"level must be one of {', '.join(LEVELS)}")
        if role is not None and role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}")
        cur = self.get(key)
        new = {"level": level or cur["level"], "role": role or cur["role"],
               "config": cur["config"] if config is None else config,
               "quiet_until": cur["quiet_until"] if quiet_until is None else quiet_until}
        with self.lock:
            self.db.execute("INSERT INTO trust(key, level, role, config, updated, quiet_until) VALUES (?,?,?,?,?,?) "
                            "ON CONFLICT(key) DO UPDATE SET level=excluded.level, role=excluded.role, "
                            "config=excluded.config, updated=excluded.updated, quiet_until=excluded.quiet_until",
                            (key, new["level"], new["role"], json.dumps(new["config"]), time.time(), new["quiet_until"]))
            self.db.commit()
        if level is not None and level != cur["level"]:
            self.log(key, "trust.changed", f"{label(key)}: {cur['level']} → {level} (by the {by})",
                     {"from": cur["level"], "to": level}, key=key)
        if role is not None and role != cur["role"]:
            self.log(key, "role.changed", f"{label(key)}: {cur['role']} → {role}", {"from": cur["role"], "to": role}, key=key)
        return self.get(key)

    # -- the record that earns trust ------------------------------------------------------------------------
    def record(self, key: str) -> dict:
        """How the user has decided this agent's proposals: counts, and the run of clean approvals (filed by the
        user without dropping or editing a note, and not undone since) that ends with the latest decision."""
        with self.lock:
            props = self.db.execute(
                "SELECT p.agent, p.status, p.review, p.auto, b.status, "
                "EXISTS (SELECT 1 FROM entries e WHERE e.batch_id = p.batch_id AND e.undone IS NOT NULL) "
                "FROM proposals p LEFT JOIN batches b ON b.id = p.batch_id WHERE p.status IN ('applied','rejected') "
                "ORDER BY p.decided DESC").fetchall()
        # a note undone one by one (K7) leaves its batch "applied" but the approval wasn't clean
        mine = [(s, rv, au, "partly undone" if part else bs) for a, s, rv, au, bs, part in props if agent_key(a) == key]
        approved = sum(1 for s, *_ in mine if s == "applied")
        streak = 0
        for s, rv, au, bs in mine:
            if au:                                  # filed by trust: the user didn't decide it
                continue
            review = json.loads(rv) if rv else None
            if s != "applied" or bs != "applied" or (review and (review.get("dropped") or review.get("edited"))):
                break
            streak += 1
        auto_undone = sum(1 for s, rv, au, bs in mine if au and bs == "undone")
        return {"decided": len(mine), "approved": approved, "rejected": len(mine) - approved, "streak": streak,
                "auto_undone": auto_undone}

    def suggestion(self, key: str, record: dict | None = None) -> str | None:
        """The next level to suggest, if the agent has earned it and the user hasn't said "not now" lately."""
        t, r = self.get(key), record or self.record(key)
        if t["level"] == "trusted" or key in ("reviewer",):
            return None
        if r["streak"] >= SUGGEST_AFTER and r["decided"] >= t["quiet_until"]:
            return LEVELS[LEVELS.index(t["level"]) + 1]
        return None

    def agents(self, seen: list[str]) -> list[dict]:
        """Every agent with a trust row, a log entry or a proposal, with its level, role and record."""
        with self.lock:
            keys = {r[0] for r in self.db.execute("SELECT key FROM trust")}
            keys |= {r[0] for r in self.db.execute("SELECT DISTINCT key FROM agent_log")}
            keys |= {agent_key(r[0]) for r in self.db.execute("SELECT DISTINCT agent FROM proposals")}
        keys |= set(seen) | {"librarian", "reviewer"}      # the built-in roles are always listed
        keys -= {"several agents", "you"}
        rows = []
        for k in keys:
            r = self.record(k)
            rows.append(self.get(k) | {"record": r, "suggest": self.suggestion(k, r)})
        return sorted(rows,
                      key=lambda a: (a["key"] not in ("digest", "librarian", "reviewer"), a["label"].lower()))
