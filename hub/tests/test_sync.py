"""Y1 (D27, D28): IDs that can't clash between devices, and this install's device identity."""
import json
import sqlite3
import threading

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
