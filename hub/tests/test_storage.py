"""D25: app data per computer, a Library (Notes + Files) that syncs, export, moving it, sync conflicts."""
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config, load
from sage_os_hub.storage import conflicts, export_notes, merge_into, move_legacy, set_local_setting

H = {"x-sage-os": "1"}


def test_paths_derive_from_data_and_library(tmp_path):
    c = Config(data_dir=tmp_path / "d")
    assert c.store == tmp_path / "d" / "hub.db" and c.vault == tmp_path / "d" / "Library" / "Notes"
    assert c.library == tmp_path / "d" / "Library" and c.engine_root == tmp_path / "d" / "engine"
    c = Config(data_dir=tmp_path / "d", library=tmp_path / "OneDrive" / "Sage")
    assert c.vault == tmp_path / "OneDrive" / "Sage" / "Notes" and c.store == tmp_path / "d" / "hub.db"
    (tmp_path / "old" / "vault").mkdir(parents=True)              # an install from before D25
    c = Config(data_dir=tmp_path / "old")
    assert c.vault == tmp_path / "old" / "vault" and c.library is None


def test_storage_from_config_files(tmp_path):
    (tmp_path / "config.toml").write_text("[hub]\nport = 9000\n", encoding="utf-8")
    set_local_setting(tmp_path / "config.local.toml", "storage", "data", str(tmp_path / "AppData" / "Sage OS"))
    set_local_setting(tmp_path / "config.local.toml", "storage", "library", str(tmp_path / "Cloud\\Sage Library"))
    set_local_setting(tmp_path / "config.local.toml", "storage", "library", str(tmp_path / "Cloud2"))   # replaced
    c = load(tmp_path / "config.toml")
    assert c.data_dir == tmp_path / "AppData" / "Sage OS" and c.vault == tmp_path / "Cloud2" / "Notes"
    assert (tmp_path / "config.local.toml").read_text().count("library =") == 1


def test_conflicts_are_found_without_false_alarms(tmp_path):
    n = tmp_path / "Notes" / "Finance"
    n.mkdir(parents=True)
    for f in ("wacc.md", "wacc-DESKTOP-AB12C.md", "dcf-formula.md", "dcf-formula-sheet.md", "npv.md", "npv 2.md",
              "irr.sync-conflict-20261009-101500-XYZ.md", "beta (the owner's conflicted copy 2026-10-09).md", "beta.md"):
        (n / f).write_text("x", encoding="utf-8")
    assert conflicts(tmp_path) == sorted(["Notes/Finance/wacc-DESKTOP-AB12C.md", "Notes/Finance/npv 2.md",
                                          "Notes/Finance/irr.sync-conflict-20261009-101500-XYZ.md",
                                          "Notes/Finance/beta (the owner's conflicted copy 2026-10-09).md"])


def test_merge_never_overwrites(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    (a / "Notes").mkdir(parents=True)
    (b / "Notes").mkdir(parents=True)
    (a / "Notes" / "one.md").write_text("mine", encoding="utf-8")
    (a / "Notes" / "two.md").write_text("same", encoding="utf-8")
    (b / "Notes" / "one.md").write_text("theirs", encoding="utf-8")
    (b / "Notes" / "two.md").write_text("same", encoding="utf-8")
    r = merge_into(a, b)
    assert r == {"copied": 0, "same": 1, "kept_both": 1}
    assert (b / "Notes" / "one.md").read_text() == "theirs"
    assert [p.name for p in (b / "Notes").glob("one (from *).md")]


def test_move_legacy_copies_checks_and_keeps_the_old_folder(tmp_path):
    old = tmp_path / "sage-os" / "data"
    (old / "vault" / "Finance").mkdir(parents=True)
    (old / "hub.db").write_bytes(b"db")
    (old / "vault" / "Finance" / "npv.md").write_text("# NPV", encoding="utf-8")
    (old / "sources" / "drive").mkdir(parents=True)
    (old / "sources" / "drive" / "a.pdf").write_bytes(b"%PDF")
    new = tmp_path / "AppData" / "Sage OS"
    r = move_legacy(old, new)
    assert r["files"] == 3 and not old.exists() and Path(r["old_kept_as"]).is_dir()
    assert (new / "Library" / "Notes" / "Finance" / "npv.md").read_text() == "# NPV"
    assert (new / "sources" / "drive" / "a.pdf").exists() and (new / "Library" / "Files").is_dir()
    with pytest.raises(SystemExit):
        move_legacy(Path(r["old_kept_as"]), new)                     # never over existing data


def test_export_zip_has_notes_and_files(tmp_path):
    (tmp_path / "Notes" / "_attachments").mkdir(parents=True)
    (tmp_path / "Notes" / "a.md").write_text("# A", encoding="utf-8")
    (tmp_path / "Notes" / "_attachments" / "fig.png").write_bytes(b"png")
    (tmp_path / "Files").mkdir()
    (tmp_path / "Files" / "deck.pptx").write_bytes(b"pk")
    names = zipfile.ZipFile(export_notes(tmp_path / "Notes", tmp_path / "Files")).namelist()
    assert sorted(names) == ["Files/deck.pptx", "Notes/_attachments/fig.png", "Notes/a.md"]


@pytest.fixture
def hub_client(tmp_path):
    app = create_app(Config(data_dir=tmp_path / "data", hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[],
                            engine_enabled=False), start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield app.state.hub, c, tmp_path


def test_library_files_are_indexed_in_place_and_never_touched(hub_client):
    hub, c, tmp = hub_client
    files = tmp / "data" / "Library" / "Files"
    assert files.is_dir() and (tmp / "data" / "Library" / "Notes").is_dir()
    (files / "Course").mkdir()
    (files / "Course" / "syllabus.md").write_text("Intermediate accounting syllabus: revenue recognition.", encoding="utf-8")
    hub.sources.sync("library")
    hits = c.get("/api/sources/search", params={"q": "revenue recognition"}).json()["results"]
    assert [h["path"] for h in hits] == ["Course/syllabus.md"] and hits[0]["source"] == "library"
    assert not (hub.sources.root / "library").exists()                 # not copied
    (files / "Course" / "syllabus.md").unlink()
    hub.sources.sync("library")
    assert c.get("/api/sources/search", params={"q": "revenue recognition"}).json()["results"] == []


def test_storage_api_info_export_and_moving_the_library(hub_client):
    hub, c, tmp = hub_client
    (hub.vault.root / "Finance").mkdir(parents=True, exist_ok=True)
    (hub.vault.root / "Finance" / "npv.md").write_text(
        "---\nuid: 01J9ZQ4V6R8T2M3N5P7Q9S1W3Y\ntitle: NPV\ncreated: 2026-10-01\nupdated: 2026-10-01\ntype: note\n"
        "status: active\norigin: human\n---\nNet present value.\n", encoding="utf-8")
    info = c.get("/api/storage").json()
    assert info["library"]["notes"] == 1 and info["data"]["path"] == str(tmp / "data")
    z = c.get("/api/storage/export")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert c.post("/api/storage/library", json={"path": "relative/path"}, headers=H).status_code == 400
    cloud = tmp / "OneDrive" / "Sage Library"
    r = c.post("/api/storage/library", json={"path": str(cloud)}, headers=H)
    assert r.status_code == 200, r.text
    assert (cloud / "Notes" / "Finance" / "npv.md").exists() and hub.vault.root == cloud / "Notes"
    assert c.get("/api/vault/search", params={"q": "present value"}).json()["results"][0]["title"] == "NPV"
    assert c.post("/api/storage/library", json={"path": str(cloud)}).status_code == 403
