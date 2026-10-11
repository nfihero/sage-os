"""Y1.6 (D28): the one-time move of a pre-0.16 install to ULIDs."""
import json
import sqlite3
from pathlib import Path

import pytest

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.sync import is_id, migrate

OLD_SCHEMAS = {
    "hub.db": """
      CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT NOT NULL,
        source TEXT NOT NULL, type TEXT NOT NULL, data TEXT NOT NULL);
      CREATE TABLE panels (name TEXT PRIMARY KEY, ts REAL NOT NULL, data TEXT NOT NULL);
      CREATE TABLE claude_sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, cwd TEXT NOT NULL, model TEXT,
        sdk_session_id TEXT, created REAL NOT NULL, updated REAL NOT NULL, cost_usd REAL NOT NULL DEFAULT 0,
        turns INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE chat_items (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, ts REAL NOT NULL,
        kind TEXT NOT NULL, data TEXT NOT NULL);
      CREATE INDEX chat_items_session ON chat_items (session_id, id);
      CREATE TABLE chat_sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, provider TEXT NOT NULL,
        model TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
      INSERT INTO claude_sessions VALUES ('cs_0566a68eff', 'Notes', 'C:/w', NULL, 'sdk-1', 100, 300, 0.5, 3);
      INSERT INTO chat_sessions VALUES ('ch_3fc44d5ca2', 'Gemma', 'engine', 'm', 200, 210);
      INSERT INTO chat_items(session_id, ts, kind, data) VALUES ('cs_0566a68eff', 101, 'user', '{}'),
        ('cs_0566a68eff', 102, 'text', '{}'), ('ch_3fc44d5ca2', 201, 'user', '{}');
      INSERT INTO events(ts, kind, source, type, data) VALUES (1, 'system', 'x', 'y', '{"session": "cs_0566a68eff"}');
    """,
    "bookshelf.db": """
      CREATE TABLE proposals(id TEXT PRIMARY KEY, agent TEXT NOT NULL, summary TEXT, created REAL,
        status TEXT NOT NULL, decided REAL, note TEXT, changes TEXT NOT NULL, bases TEXT NOT NULL,
        batch_id INTEGER, screened TEXT, original TEXT, review TEXT);
      CREATE TABLE batches(id INTEGER PRIMARY KEY, proposal_id TEXT, agent TEXT, summary TEXT,
        status TEXT NOT NULL, started REAL, finished REAL, undone REAL);
      CREATE TABLE entries(batch_id INTEGER, seq INTEGER, path TEXT NOT NULL, before BLOB, after BLOB,
        PRIMARY KEY(batch_id, seq));
      INSERT INTO proposals VALUES ('p_00059f8eff', 'claude:cs_0566a68eff', 's', 150, 'applied', 151, NULL,
        '[]', '{}', 1, NULL, NULL, NULL);
      INSERT INTO proposals VALUES ('p_b51d776a77', 'digest:file:gemma', 's', 400, 'pending', NULL, NULL,
        '[]', '{}', NULL, NULL, NULL, NULL);
      INSERT INTO batches VALUES (1, 'p_00059f8eff', 'claude:cs_0566a68eff', 's', 'applied', 151, 152, NULL);
      INSERT INTO entries VALUES (1, 0, 'a.md', NULL, X'6869'), (1, 1, 'b.md', X'00', X'01');
    """,
    "digest.db": """
      CREATE TABLE jobs(id TEXT PRIMARY KEY, source TEXT, rel TEXT, title TEXT, provider TEXT, model TEXT,
        status TEXT, created REAL, updated REAL, chars INTEGER, error TEXT);
      CREATE TABLE secs(job TEXT, idx INTEGER, chapter TEXT, title TEXT, pages TEXT, text TEXT, status TEXT,
        concepts TEXT, covered TEXT, notes TEXT, attempts INTEGER DEFAULT 0, error TEXT, ms INTEGER,
        proposed INTEGER DEFAULT 0, PRIMARY KEY(job, idx));
      CREATE TABLE chapters(job TEXT, chapter TEXT, ord INTEGER, status TEXT, proposals TEXT, error TEXT,
        PRIMARY KEY(job, chapter));
      INSERT INTO jobs VALUES ('dg_7cbf09dbad', 'gdrive', 'book.pdf', 'Book', 'engine', 'm', 'running', 390, 400, 10, NULL);
      INSERT INTO secs(job, idx, chapter, title, text, status) VALUES ('dg_7cbf09dbad', 0, '1', 't', 'x', 'drafted'),
        ('dg_7cbf09dbad', 1, '1', 't', 'y', 'drafted');
      INSERT INTO chapters VALUES ('dg_7cbf09dbad', '1', 0, 'sent', '["p_b51d776a77"]', NULL);
    """,
    "briefings.db": """
      CREATE TABLE briefings(id INTEGER PRIMARY KEY AUTOINCREMENT, chat TEXT NOT NULL, ts REAL NOT NULL,
        agent TEXT, session TEXT, query TEXT NOT NULL, terms TEXT NOT NULL, items TEXT NOT NULL);
      CREATE INDEX briefings_chat ON briefings(chat, id);
      CREATE TABLE briefing_chats(chat TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
        drops TEXT NOT NULL DEFAULT '[]', owed TEXT NOT NULL DEFAULT '[]');
      INSERT INTO briefings(chat, ts, agent, session, query, terms, items) VALUES
        ('claude:cs_0566a68eff', 101, 'claude', 'cs_0566a68eff', 'q', '[]', '{"items": []}'),
        ('chat:ch_3fc44d5ca2', 201, 'chat', 'ch_3fc44d5ca2', 'q', '[]', '{"items": []}');
      INSERT INTO briefing_chats VALUES ('claude:cs_0566a68eff', 0, '[]', '[]');
    """,
}


def old_install(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, sql in OLD_SCHEMAS.items():
        paths[name] = folder / name
        with sqlite3.connect(paths[name]) as con:
            con.executescript(sql)
    return paths


def q(path, sql):
    con = sqlite3.connect(path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_every_record_gets_a_ulid_and_every_reference_follows(tmp_path):
    paths = old_install(tmp_path / "data")
    report = migrate.run(paths, tmp_path / "data" / "backups", "dv_TEST")
    assert report["changed"] == {"claude_sessions": 1, "chat_sessions": 1, "proposals": 2, "jobs": 1,
                                 "chat_items": 3, "batches": 1, "briefings": 2}
    hub, shelf, dig, brief = (paths[n] for n in ("hub.db", "bookshelf.db", "digest.db", "briefings.db"))
    [(cs,)] = q(hub, "SELECT id FROM claude_sessions")
    [(ch,)] = q(hub, "SELECT id FROM chat_sessions")
    assert is_id(cs, "cs_") and is_id(ch, "ch_")
    items = q(hub, "SELECT id, session_id FROM chat_items ORDER BY id")
    assert [s for _, s in items] == [cs, cs, ch] and all(is_id(i, "ci_") for i, _ in items)    # still in time order
    [(pa, agent, bref), (pb, _, _)] = q(shelf, "SELECT id, agent, batch_id FROM proposals ORDER BY created")
    [(bid, bprop, bagent)] = q(shelf, "SELECT id, proposal_id, agent FROM batches")
    assert agent == bagent == f"claude:{cs}" and bref == bid and bprop == pa and is_id(bid, "b_")
    assert q(shelf, "SELECT batch_id, seq, after FROM entries ORDER BY seq") == [(bid, 0, b"hi"), (bid, 1, b"\x01")]
    [(job,)] = q(dig, "SELECT id FROM jobs")
    assert q(dig, "SELECT DISTINCT job FROM secs") == [(job,)]
    assert q(dig, "SELECT job, proposals FROM chapters") == [(job, json.dumps([pb]))]
    assert sorted(q(brief, "SELECT chat, session FROM briefings")) == sorted([(f"claude:{cs}", cs), (f"chat:{ch}", ch)])
    assert q(brief, "SELECT chat, enabled FROM briefing_chats") == [(f"claude:{cs}", 0)]
    assert "cs_0566a68eff" in q(hub, "SELECT data FROM events")[0][0]        # this computer only: left alone
    # every synced row went into the change log once, from this device
    logged = q(shelf, "SELECT stream, count(*), min(device) FROM changes GROUP BY stream ORDER BY stream")
    assert logged == [("batches", 1, "dv_TEST"), ("entries", 2, "dv_TEST"), ("proposals", 2, "dv_TEST")]
    assert q(dig, "SELECT count(*) FROM changes WHERE stream='secs'") == [(2,)]
    saved = json.loads((Path(report["backup"]) / "id-map.json").read_text(encoding="utf-8"))
    assert saved["map"]["claude_sessions"] == {"cs_0566a68eff": cs}
    assert q(Path(report["backup"]) / "hub.db", "SELECT id FROM claude_sessions") == [("cs_0566a68eff",)]


def test_a_second_run_changes_nothing(tmp_path):
    paths = old_install(tmp_path / "data")
    migrate.run(paths, tmp_path / "data" / "backups", "dv_TEST")
    snap = {n: q(p, "SELECT * FROM changes ORDER BY id") for n, p in paths.items()}
    assert migrate.run(paths, tmp_path / "data" / "backups", "dv_TEST") is None
    assert {n: q(p, "SELECT * FROM changes ORDER BY id") for n, p in paths.items()} == snap
    assert len(list((tmp_path / "data" / "backups").iterdir())) == 1


def test_a_failed_migration_puts_everything_back(tmp_path, monkeypatch):
    paths = old_install(tmp_path / "data")
    snap = {n: (q(p, "SELECT sql FROM sqlite_master ORDER BY name"), q(p, "SELECT count(*) FROM sqlite_master"))
            for n, p in paths.items()}
    real = migrate._rewrite

    def broken(cons, maps):
        real(cons, maps)
        raise RuntimeError("disk full")
    monkeypatch.setattr(migrate, "_rewrite", broken)
    with pytest.raises(RuntimeError):
        migrate.run(paths, tmp_path / "data" / "backups", "dv_TEST")
    assert {n: (q(p, "SELECT sql FROM sqlite_master ORDER BY name"), q(p, "SELECT count(*) FROM sqlite_master"))
            for n, p in paths.items()} == snap
    assert q(paths["hub.db"], "SELECT id FROM claude_sessions") == [("cs_0566a68eff",)]
    assert q(paths["bookshelf.db"], "SELECT id FROM batches") == [(1,)]


def test_the_hub_starts_on_an_old_install_and_carries_on(tmp_path):
    old_install(tmp_path / "data")
    cfg = Config(data_dir=tmp_path / "data", hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[],
                 engine_enabled=False)
    hub = create_app(cfg, start_adapters=False).state.hub
    assert hub.migration and hub.migration["changed"]["chat_items"] == 3
    [s] = hub.store.claude_sessions()
    assert is_id(s["id"], "cs_") and s["sdk_session_id"] == "sdk-1"
    assert [i["kind"] for i in hub.store.chat_items(s["id"])] == ["user", "text"]
    new = hub.store.add_chat_item(s["id"], "user", {"text": "after"})
    assert hub.store.chat_items(s["id"])[-1]["id"] == new["id"]                 # new items sort after old ones
    [b] = hub.writer.history()
    assert b["status"] == "applied" and [f["path"] for f in b["files"]] == ["a.md", "b.md"]
    assert hub.writer.proposal(b["proposal_id"])["status"] == "applied"
    assert hub.digests.db.execute("SELECT count(*) FROM secs").fetchone() == (2,)
