"""Y1 (D27, D28): IDs that can't clash between devices, and this install's device identity."""
import json
import re
import sqlite3
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.sync import Device, is_id, manifest, new_id
from sage_os_hub.sync.ids import ALPHABET, Generator, id_time, ulid

H = {"X-Sage-OS": "1"}


# -- Y1.2 IDs ---------------------------------------------------------------------------------------------
def test_ids_are_unique_and_in_order_even_within_one_millisecond():
    ids = [ulid() for _ in range(100_000)]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)
    assert all(len(i) == 26 and set(i) <= set(ALPHABET) for i in ids[:1000])


def test_ids_stay_in_order_when_the_clock_steps_back():
    gen = Generator()
    a = gen(now_ms=2_000_000_000_000)
    b = gen(now_ms=1_999_999_999_000)          # clock went back a second
    assert b > a


def test_ids_from_many_threads_never_clash():
    out: list[str] = []
    lock = threading.Lock()

    def work():
        mine = [new_id("x_") for _ in range(5000)]
        with lock:
            out.extend(mine)
    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(out)) == 40_000


def test_prefix_check_and_time_read_back():
    i = new_id("ch_")
    assert is_id(i, "ch_") and not is_id(i, "cs_") and not is_id("ch_" + "a" * 10, "ch_")
    assert not is_id("ch_" + "I" * 26, "ch_")    # I, L, O, U aren't in the alphabet
    assert abs(id_time(Generator()(now_ms=1_791_000_000_123)) - 1_791_000_000.123) < 1e-6


# -- Y1.1 device identity ---------------------------------------------------------------------------------
def test_device_is_made_once_and_kept(tmp_path):
    d1 = Device.load(tmp_path)
    assert is_id(d1.id, "dv_") and d1.name
    d2 = Device.load(tmp_path)
    assert (d2.id, d2.name, d2.created) == (d1.id, d1.name, d1.created)


def test_a_fresh_app_data_folder_is_a_new_device(tmp_path):
    assert Device.load(tmp_path / "a").id != Device.load(tmp_path / "b").id


def test_rename_keeps_the_id(tmp_path):
    d = Device.load(tmp_path)
    d.rename("  the owner's   gaming PC  ")
    again = Device.load(tmp_path)
    assert again.id == d.id and again.name == "the owner's gaming PC"


def test_a_damaged_device_file_is_kept_aside_not_deleted(tmp_path):
    (tmp_path / "device.json").write_text("{not json", encoding="utf-8")
    d = Device.load(tmp_path)
    assert is_id(d.id, "dv_")
    kept = list(tmp_path.glob("device.damaged-*.json"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == "{not json"
    assert json.loads((tmp_path / "device.json").read_text(encoding="utf-8"))["id"] == d.id


def test_storage_api_shows_and_renames_the_device(tmp_path):
    cfg = Config(data_dir=tmp_path / "data", hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[],
                 engine_enabled=False)
    with TestClient(create_app(cfg, start_adapters=False), base_url="http://127.0.0.1") as c:
        dev = c.get("/api/storage").json()["device"]
        assert is_id(dev["id"], "dv_")
        assert c.post("/api/storage/device", json={"name": "Desk"}).status_code == 403     # write routes need the header
        r = c.post("/api/storage/device", json={"name": "Desk"}, headers=H)
        assert r.status_code == 200 and r.json() == dev | {"name": "Desk"}
        assert c.post("/api/storage/device", json={"name": "   "}, headers=H).status_code == 400
        assert c.get("/api/storage").json()["device"]["name"] == "Desk"


# -- Y1.3 what syncs ---------------------------------------------------------------------------------------
def _fresh_app_data(tmp_path):
    """Everything a fresh hub creates in app data, after touching the routes that make files."""
    cfg = Config(data_dir=tmp_path / "data", hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[],
                 engine_enabled=False)
    with TestClient(create_app(cfg, start_adapters=False), base_url="http://127.0.0.1") as c:
        c.get("/api/storage")
    return cfg.data_dir


def test_every_table_and_file_in_app_data_is_labelled(tmp_path):
    data = _fresh_app_data(tmp_path)
    unlabelled = [p.name for p in data.iterdir() if manifest.file_kind(p.name) is None]
    assert not unlabelled, f"label these in sync/manifest.py FILES: {unlabelled}"
    for db in data.glob("*.db"):
        with sqlite3.connect(db) as con:
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        missing = [t for t in tables if manifest.table_kind(db.name, t) is None]
        assert not missing, f"label these tables of {db.name} in sync/manifest.py TABLES: {missing}"


def test_the_manifest_names_only_tables_that_exist(tmp_path):
    data = _fresh_app_data(tmp_path)
    for db, tables in manifest.synced_tables().items():
        with sqlite3.connect(data / db) as con:
            have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert set(tables) <= have, f"{db}: {set(tables) - have} listed but not created"


def test_secrets_indexes_and_identity_never_sync():
    for name in ("google-token.json", "client_secret_123.apps.googleusercontent.com.json", "device.json",
                 "engine", "sources", "bookshelf-index.db", "sources-index.db", "hub.db-wal"):
        assert manifest.file_kind(name) == manifest.LOCAL, name
    assert manifest.table_kind("hub.db", "events") == manifest.LOCAL
    assert manifest.table_kind("bookshelf-index.db", "fts_data") == manifest.LOCAL
    assert manifest.table_kind("hub.db", "chat_items") == manifest.SYNCED
    assert manifest.table_kind("hub.db", "no_such_table") is None


# -- Y1.4 change log --------------------------------------------------------------------------------------
def _hub(tmp_path, name="data"):
    cfg = Config(data_dir=tmp_path / name, hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[],
                 engine_enabled=False)
    app = create_app(cfg, start_adapters=False)
    return app.state.hub


def test_each_synced_write_logs_exactly_one_entry(tmp_path):
    hub = _hub(tmp_path)
    log = hub.changelogs["hub.db"]
    hub.store.upsert_chat_session({"id": "ch_1", "title": "Plan", "provider": "engine", "model": "m",
                                   "created": 1.0, "updated": 1.0})
    item = hub.store.add_chat_item("ch_1", "user", {"text": "hi"})
    hub.store.upsert_chat_session({"id": "ch_1", "title": "Plan 2", "provider": "engine", "model": "m",
                                   "created": 1.0, "updated": 2.0})
    hub.store.add_event("system", "test", "x", {})          # this computer only: not logged
    hub.store.save_panel("gpu", {})
    es = log.entries()
    assert [(e["stream"], e["op"]) for e in es] == [("chat_sessions", "upsert"), ("chat_items", "upsert"),
                                                     ("chat_sessions", "upsert")]
    assert all(e["device"] == hub.device.id and is_id(e["id"]) for e in es)
    assert es[0]["record"] == "ch_1" and es[2]["data"]["title"] == "Plan 2"
    assert es[1]["record"] == str(item["id"]) and json.loads(es[1]["data"]["data"]) == {"text": "hi"}
    assert [e["id"] for e in es] == sorted(e["id"] for e in es)


def test_a_failed_write_logs_nothing(tmp_path):
    hub = _hub(tmp_path)
    con = hub.store._db
    con.execute("INSERT INTO chat_sessions (id, title, provider, model, created, updated) VALUES ('a','t','p','m',1,1)")
    con.rollback()
    assert hub.changelogs["hub.db"].entries() == []


def test_composite_keys_blobs_and_deletes(tmp_path):
    hub = _hub(tmp_path)
    con, log = hub.writer.db, hub.changelogs["bookshelf.db"]
    con.execute("INSERT INTO entries(batch_id, seq, path, before, after) VALUES (7, 1, 'a/b.md', NULL, ?)", (b"\x00\xffhi",))
    con.execute("DELETE FROM entries WHERE batch_id=7")
    con.commit()
    put, gone = log.entries()
    assert put["record"] == "[7,1]" and put["data"]["after"] == {"$hex": "00FF6869"} and put["data"]["before"] is None
    assert gone["op"] == "delete" and gone["record"] == "[7,1]" and gone["data"] is None


def test_quiet_writes_are_not_logged(tmp_path):
    hub = _hub(tmp_path)
    log = hub.changelogs["digest.db"]
    with log.quiet():
        hub.digests.db.execute("INSERT INTO jobs(id, status) VALUES ('dg_x', 'done')")
        hub.digests.db.commit()
    assert log.entries() == []


def test_every_database_with_synced_tables_gets_a_log(tmp_path):
    hub = _hub(tmp_path)
    assert set(hub.changelogs) == set(manifest.synced_tables())
    for name, log in hub.changelogs.items():
        assert set(log.streams) == set(manifest.synced_tables()[name])
        assert manifest.table_kind(name, "changes") == manifest.LOG


def test_entries_from_another_device_merge_in_any_order(tmp_path):
    a, b = _hub(tmp_path, "a"), _hub(tmp_path, "b")
    assert a.device.id != b.device.id
    la, lb = a.changelogs["bookshelf.db"], b.changelogs["bookshelf.db"]
    a.writer.db.execute("INSERT INTO entries(batch_id, seq, path, before, after) VALUES (1, 1, 'n.md', NULL, ?)", (b"v1",))
    a.writer.db.commit()
    a.writer.db.execute("UPDATE entries SET after=? WHERE batch_id=1", (b"v2",))
    a.writer.db.commit()
    first, second = la.entries()
    assert lb.apply([second, first]) == 2                     # out of order
    assert lb.apply([first, second]) == 0                     # again: nothing new
    assert b.writer.db.execute("SELECT after FROM entries").fetchall() == [(b"v2",)]
    assert lb.entries() == la.entries()                       # same log, original ids and device kept
    # b's next change to the record sorts after what it received, even if a's clock ran ahead
    b.writer.db.execute("UPDATE entries SET after=? WHERE batch_id=1", (b"v3",))
    b.writer.db.commit()
    assert lb.entries()[-1]["id"] > second["id"] and lb.entries()[-1]["device"] == b.device.id


# -- Y1.5 tombstones --------------------------------------------------------------------------------------
def test_deleting_a_chat_leaves_a_tombstone_that_survives_restart_and_late_writes(tmp_path):
    hub = _hub(tmp_path)
    row = {"id": "ch_1", "title": "Plan", "provider": "engine", "model": "m", "created": 1.0, "updated": 1.0}
    hub.store.upsert_chat_session(row)
    assert hub.store.delete_chat_session("ch_1") and not hub.store.delete_chat_session("ch_1")
    hub.store.upsert_chat_session(row | {"updated": 9.0})          # a reply finishing after the delete
    assert hub.store.chat_sessions() == [] and hub.store.chat_session("ch_1") is None
    last = hub.changelogs["hub.db"].entries()[-1]
    assert last["op"] == "upsert" and last["data"]["deleted"] is not None     # deletes travel as updates
    hub.store.close()
    again = _hub(tmp_path)
    assert again.store.chat_sessions() == []
    assert again.store._db.execute("SELECT count(*) FROM chat_sessions").fetchone()[0] == 1     # the row is kept


def test_a_claude_session_tombstone(tmp_path):
    hub = _hub(tmp_path)
    hub.store.upsert_claude_session({"id": "cs_1", "title": "t", "cwd": ".", "created": 1, "updated": 1,
                                     "cost_usd": 0, "turns": 0})
    hub.store.delete_claude_session("cs_1")
    assert hub.store.claude_sessions() == []


def test_a_forgotten_briefing_is_hidden_not_deleted(tmp_path):
    hub = _hub(tmp_path)
    db = hub.briefings.db
    bid = db.execute("INSERT INTO briefings(chat, ts, query, terms, items) VALUES ('c', 1, 'q', '[]', '{\"items\": []}')").lastrowid
    db.commit()
    hub.briefings.forget(bid)
    assert db.execute("SELECT count(*) FROM briefings WHERE deleted IS NOT NULL").fetchone()[0] == 1
    assert hub.briefings.latest("c") is None and hub.briefings.list("c") == []


def test_no_code_hard_deletes_a_synced_record():
    """Deleting means a tombstone (Y1.5). Only the change log's merge may remove a row, when another device
    says so."""
    root = Path(__file__).resolve().parents[1] / "sage_os_hub"
    synced = {t for ts in manifest.synced_tables().values() for t in ts}
    found = []
    for py in root.rglob("*.py"):
        if py.name == "changelog.py":
            continue
        text = py.read_text(encoding="utf-8")
        for m in re.finditer(r"DELETE\s+FROM\s+(\w+)", text, re.I):
            if m.group(1) in synced:
                found.append(f"{py.relative_to(root)}: {m.group(0)}")
    assert not found, found
