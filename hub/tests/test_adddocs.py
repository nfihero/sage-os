"""O0: adding documents from the app, with no config file or Explorer: files into the Bookshelf, folders as sources."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sage_os_hub import adddocs
from sage_os_hub.app import create_app
from sage_os_hub.config import Config

H = {"X-Sage-OS": "1"}


@pytest.fixture
def chat(tmp_path):
    """A fresh install's hub: app data and a Bookshelf folder, nothing connected."""
    c = Config(data_dir=tmp_path / "d", local_config=tmp_path / "d" / "config.local.toml", claude_enabled=False,
               hermes_profiles=[], engine_root=tmp_path / "engine")
    app = create_app(c, start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield app.state.hub, client, []


def wait_synced(hub, name, timeout=10):
    for _ in range(int(timeout / 0.1)):
        info = next((s for s in hub.sources.summary()["sources"] if s["name"] == name), None)
        if info and info.get("last_sync") and not hub.sources.syncing:
            return info
        time.sleep(0.1)
    raise AssertionError(f"{name} never synced")


def test_added_files_land_in_the_bookshelf_and_become_searchable(chat):
    hub, client, rounds = chat
    files = Path(hub.sources.specs["library"].path)
    body = b"# Term sheet\nThe liquidation preference is 1x non-participating.\n"
    assert client.post("/api/bookshelf/files?name=term-sheet.md", content=body).status_code == 403
    r = client.post("/api/bookshelf/files?name=term-sheet.md", content=body, headers=H).json()
    assert r["saved"] == "term-sheet.md" and (files / "term-sheet.md").read_bytes() == body
    r = client.post("/api/bookshelf/files?name=term-sheet.md", content=b"other", headers=H).json()
    assert r["saved"] == "term-sheet (2).md"                                   # never overwrites
    r = client.post("/api/bookshelf/files?name=..%2F..%2Fescape.txt", content=b"x", headers=H).json()
    assert r["saved"] == "escape.txt" and (files / "escape.txt").exists()       # no folders in a name
    wait_synced(hub, "library")
    hits = client.get("/api/sources/search?q=liquidation").json()["results"]
    assert any(h["path"] == "term-sheet.md" for h in hits)
    assert not list(files.glob("*.part"))


def test_a_folder_becomes_a_source_and_is_remembered(chat, tmp_path):
    hub, client, rounds = chat
    docs = tmp_path / "My Deals"
    docs.mkdir()
    (docs / "memo.md").write_text("# Memo\nEBITDA multiple of 9.5x for the platform deal.\n", encoding="utf-8")
    r = client.post("/api/bookshelf/folders", json={"path": str(docs)}, headers=H).json()
    assert r == {"name": "my-deals", "path": str(docs.resolve()), "added": True}
    assert "name = 'my-deals'" in hub.cfg.local_config.read_text(encoding="utf-8")
    assert client.post("/api/bookshelf/folders", json={"path": str(docs)}, headers=H).json()["added"] is False
    wait_synced(hub, "my-deals")
    assert any(h["source"] == "my-deals" for h in client.get("/api/sources/search?q=EBITDA").json()["results"])
    bad = client.post("/api/bookshelf/folders", json={"path": str(hub.cfg.data_dir)}, headers=H)
    assert bad.status_code == 400 and "Sage OS's own folder" in bad.text
    assert client.post("/api/bookshelf/folders", json={"path": str(tmp_path / "nope")}, headers=H).status_code == 400


def test_the_folder_picker_can_be_cancelled(chat, monkeypatch):
    hub, client, rounds = chat
    monkeypatch.setattr(adddocs, "pick_folder", lambda: None)
    assert client.post("/api/bookshelf/folders", json={}, headers=H).json() == {"cancelled": True}


def test_safe_names():
    bs = chr(92)
    assert adddocs.safe_name("C:/x/report.pdf") == "report.pdf"
    assert adddocs.safe_name(f"C:{bs}x{bs}report.pdf") == "report.pdf"
    assert adddocs.safe_name("con.txt") == "document_con.txt"
    assert adddocs.safe_name('a<b>:"c".txt') == "a_b___c_.txt"
