"""Hermes kanban board, read from kanban.db (read-only; the one allowed shortcut past the CLI)."""
from __future__ import annotations

import json

from ..sqlite_ro import columns, connect_ro
from .base import Adapter

BOARD_COLS = ["id", "title", "assignee", "status", "priority", "created_by", "created_at",
              "started_at", "completed_at", "model_override", "block_kind", "consecutive_failures",
              "last_heartbeat_at", "current_run_id", "session_id", "goal_mode"]
REQUIRED = {"tasks": {"id", "title", "status", "assignee", "created_at"},
            "task_events": {"id", "task_id", "kind", "payload", "created_at"},
            "task_runs": {"id", "task_id", "status", "started_at"},
            "task_comments": {"task_id", "author", "body", "created_at"},
            "task_links": {"parent_id", "child_id"}}
QUIET_EVENTS = {"heartbeat"}          # streamed for the pulse, never stored


def _payload(raw):
    try:
        return json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return raw


class KanbanAdapter(Adapter):
    name = "kanban"

    def __init__(self, emit, hermes_home, interval=5.0):
        super().__init__(emit)
        self.db = hermes_home / "kanban.db"
        self.interval = interval
        self.last_event_id: int | None = None
        self._fingerprint = None

    def smoke(self):
        if not self.db.exists():
            return [("kanban.db present", False, str(self.db))]
        out = [("kanban.db present", True, str(self.db))]
        with connect_ro(self.db) as con:
            for table, need in REQUIRED.items():
                missing = need - columns(con, table)
                out.append((f"kanban.{table} columns", not missing,
                            "ok" if not missing else f"missing {sorted(missing)}"))
        return out

    def poll(self):
        if not self.db.exists():                      # no Hermes board on this computer (a fresh install): nothing to read
            if self._fingerprint != "absent":
                self._fingerprint = "absent"
                self.emit.panel("board", {"tasks": [], "archived": 0, "links": []})
            return
        with connect_ro(self.db) as con:
            have = columns(con, "tasks")
            cols = [c for c in BOARD_COLS if c in have]
            tasks = [dict(r) for r in con.execute(
                f"SELECT {', '.join(cols)} FROM tasks WHERE status != 'archived' "
                "ORDER BY priority DESC, created_at DESC")]
            archived = con.execute("SELECT COUNT(*) FROM tasks WHERE status = 'archived'").fetchone()[0]
            links = [dict(r) for r in con.execute("SELECT parent_id, child_id FROM task_links")]
            for t in tasks:
                if t["status"] == "blocked":
                    row = con.execute("SELECT payload FROM task_events WHERE task_id = ? AND kind = 'blocked' "
                                      "ORDER BY id DESC LIMIT 1", (t["id"],)).fetchone()
                    p = _payload(row[0]) if row else None
                    t["block_reason"] = p.get("reason") if isinstance(p, dict) else p
            max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM task_events").fetchone()[0]
            new = []
            if self.last_event_id is not None and max_id > self.last_event_id:
                new = [dict(r) for r in con.execute(
                    "SELECT e.id, e.task_id, e.run_id, e.kind, e.payload, e.created_at, t.title "
                    "FROM task_events e LEFT JOIN tasks t ON t.id = e.task_id "
                    "WHERE e.id > ? ORDER BY e.id LIMIT 500", (self.last_event_id,))]
        self.last_event_id = max_id

        live = {t["id"] for t in tasks}
        board = {"tasks": tasks, "archived": archived,
                 "links": [l for l in links if l["parent_id"] in live or l["child_id"] in live]}
        fp = json.dumps(board, sort_keys=True, default=str)
        if fp != self._fingerprint:
            self._fingerprint = fp
            self.emit.panel("board", board)

        for e in new:
            self.emit.event("task", self.name, f"task.{e['kind']}", {
                "task_id": e["task_id"], "title": e["title"], "run_id": e["run_id"],
                "payload": _payload(e["payload"]), "event_id": e["id"]},
                persist=e["kind"] not in QUIET_EVENTS, ts=e["created_at"])

    def task_detail(self, task_id: str) -> dict | None:
        with connect_ro(self.db) as con:
            row = con.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            task = dict(row)
            task.pop("claim_lock", None)
            runs = [dict(r) for r in con.execute(
                "SELECT * FROM task_runs WHERE task_id = ? ORDER BY id", (task_id,))]
            events = [dict(r) | {"payload": _payload(r["payload"])} for r in con.execute(
                "SELECT id, run_id, kind, payload, created_at FROM task_events "
                "WHERE task_id = ? ORDER BY id", (task_id,))]
            comments = [dict(r) for r in con.execute(
                "SELECT author, body, created_at FROM task_comments WHERE task_id = ? ORDER BY id",
                (task_id,))]
            parents = [r[0] for r in con.execute(
                "SELECT parent_id FROM task_links WHERE child_id = ?", (task_id,))]
            children = [r[0] for r in con.execute(
                "SELECT child_id FROM task_links WHERE parent_id = ?", (task_id,))]
        for r in runs:
            r.pop("claim_lock", None)
            r["metadata"] = _payload(r.get("metadata"))
        # Collapse heartbeat noise: keep a count per run instead of hundreds of rows.
        beats: dict = {}
        kept = []
        for e in events:
            if e["kind"] in QUIET_EVENTS:
                beats[e["run_id"]] = beats.get(e["run_id"], 0) + 1
            else:
                kept.append(e)
        return {"task": task, "runs": runs, "events": kept, "heartbeats": beats,
                "comments": comments, "parents": parents, "children": children}
