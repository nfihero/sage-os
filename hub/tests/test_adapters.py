"""Adapter tests against throwaway copies of the Hermes file shapes (no live Hermes needed)."""
import json
import sqlite3

import pytest

from sage_os_hub.adapters.kanban import KanbanAdapter
from sage_os_hub.adapters.safety import LogTail, SafetyAdapter, normalize
from sage_os_hub.adapters.sessions import SessionsAdapter
from sage_os_hub.config import Config
from sage_os_hub.sqlite_ro import connect_ro
from sage_os_hub.store import Store


class Rec:
    def __init__(self):
        self.panels, self.events = {}, []

    def panel(self, name, data, *, broadcast=True):
        self.panels[name] = data

    def event(self, kind, source, type_, data, *, persist=True, ts=None):
        self.events.append((kind, type_, data, persist))


@pytest.fixture
def home(tmp_path):
    k = sqlite3.connect(tmp_path / "kanban.db")
    k.executescript("""
      CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT, status TEXT,
        priority INTEGER DEFAULT 0, created_at INTEGER, claim_lock TEXT, block_kind TEXT);
      CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER,
        kind TEXT, payload TEXT, created_at INTEGER);
      CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, status TEXT, started_at INTEGER,
        claim_lock TEXT, metadata TEXT);
      CREATE TABLE task_comments (id INTEGER PRIMARY KEY, task_id TEXT, author TEXT, body TEXT, created_at INTEGER);
      CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
      INSERT INTO tasks VALUES ('t1','Parser','body','sage','running',0,100,'lock',NULL);
      INSERT INTO tasks VALUES ('t2','Old','','sage','archived',0,50,NULL,NULL);
      INSERT INTO task_events (task_id, run_id, kind, payload, created_at) VALUES ('t1',1,'created',NULL,100);
      INSERT INTO task_runs VALUES (1,'t1','running',101,'lock','{"a":1}');
    """)
    k.commit(), k.close()
    (tmp_path / "profiles" / "sage").mkdir(parents=True)
    for db in (tmp_path / "state.db", tmp_path / "profiles" / "sage" / "state.db"):
        s = sqlite3.connect(db)
        s.execute("CREATE TABLE sessions (id TEXT, source TEXT, title TEXT, model TEXT, started_at REAL,"
                  " last_activity_at REAL, hidden INTEGER DEFAULT 0)")
        s.execute("INSERT INTO sessions VALUES ('s1','tui','Finance','qwen',1.0,2.0,0)")
        s.commit(), s.close()
    (tmp_path / "logs").mkdir()
    return tmp_path


def test_kanban_board_and_new_events(home):
    rec = Rec()
    a = KanbanAdapter(rec, home)
    assert all(ok for _, ok, _ in a.smoke())
    a.poll()
    assert [t["id"] for t in rec.panels["board"]["tasks"]] == ["t1"]
    assert rec.panels["board"]["archived"] == 1
    assert rec.events == []                     # history is not replayed on first poll
    con = sqlite3.connect(home / "kanban.db")
    con.execute("INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                "VALUES ('t1',1,'blocked','{\"kind\":\"needs_input\"}',110)")
    con.execute("INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                "VALUES ('t1',1,'heartbeat',NULL,111)")
    con.commit(), con.close()
    a.poll()
    assert [(e[1], e[3]) for e in rec.events] == [("task.blocked", True), ("task.heartbeat", False)]
    assert rec.events[0][2]["payload"] == {"kind": "needs_input"}


def test_task_detail_hides_locks_and_collapses_heartbeats(home):
    d = KanbanAdapter(Rec(), home).task_detail("t1")
    assert "claim_lock" not in d["task"] and "claim_lock" not in d["runs"][0]
    assert d["runs"][0]["metadata"] == {"a": 1}
    assert KanbanAdapter(Rec(), home).task_detail("nope") is None


def test_readonly_connection_refuses_writes(home):
    with connect_ro(home / "kanban.db") as con, pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM tasks")


def test_logtail_handles_partial_lines_and_truncation(tmp_path):
    p = tmp_path / "g.log"
    p.write_text('{"event":"allow","ts":"2026-09-29T19:56:29+00:00"}\n', encoding="utf-8")
    t = LogTail(p)
    assert len(t.initial(10)) == 1
    with p.open("a", encoding="utf-8") as f:
        f.write('{"event":"block","te')
    assert t.read_new() == []
    with p.open("a", encoding="utf-8") as f:
        f.write('xt":"rm -rf G:/"}\n')
    assert t.read_new() == [{"event": "block", "text": "rm -rf G:/"}]
    p.write_text('{"event":"allow"}\n', encoding="utf-8")        # truncated / rotated
    assert t.read_new() == [{"event": "allow"}]


def test_safety_feed_streams_blocks(home):
    cfg = Config(hermes_home=home)
    rec = Rec()
    a = SafetyAdapter(rec, cfg)
    a.poll()
    assert rec.panels["safety"] == []
    with (home / "logs" / "write-guard.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "block", "tool": "write_file", "targets": ["G:/x"],
                            "reason": "drive is read-only", "ts": "2026-09-29T20:00:00+00:00"}) + "\n")
    a.poll()
    kind, type_, data, persist = rec.events[0]
    assert type_ == "guard.block" and persist and data["gate"] == "write-guard" and data["detail"] == "G:/x"


def test_normalize_guardian_record():
    e = normalize("guardian", {"event": "allow", "tool": "terminal", "ms": 5, "text": "ls", "ts": 10})
    assert (e["detail"], e["ts"], e["ms"]) == ("ls", 10.0, 5)


def test_sessions_per_profile_pinned_first(home):
    rec = Rec()
    SessionsAdapter(rec, Config(hermes_home=home, pinned_profiles=["sage"])).poll()
    assert [p["profile"] for p in rec.panels["sessions"]] == ["sage", "default"]


def test_store_roundtrip(tmp_path):
    s = Store(tmp_path / "hub.db")
    e = s.add_event("task", "kanban", "task.created", {"task_id": "t1"})
    assert s.events_after(0)[0]["data"] == {"task_id": "t1"} and s.events_after(e["id"]) == []
    s.save_panel("board", {"tasks": []})
    assert s.load_panels() == {"board": {"tasks": []}}
