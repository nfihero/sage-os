"""Bookshelf K3: propose -> approve in the inbox -> single writer with journal and exact undo."""
import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.knowledge import ProposalError, StaleProposal, Vault, Writer
from sage_os_hub.knowledge import writer as writer_module
from sage_os_hub.knowledge.proposals import new_ulid, slugify
from sage_os_hub.knowledge.vault import ULID, parse_note

HUMAN = "01J9ZQ4V6R8T2M3N5P7Q9S1W3Y"
AGENT = "claude:cs_test"
H = {"x-sage-os": "1"}


def human_note(extra=""):
    return (f"---\nuid: {HUMAN}\ntitle: DCF formula sheet\ncreated: 2026-03-14\nupdated: 2026-03-14\ntype: reference\n"
            f"status: active\norigin: human\ncustom_plugin_key: keep me\n{extra}---\n# DCF\n\nMy own words.\n").encode()


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def w(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    (v.root / "Finance").mkdir()
    (v.root / "Finance" / "dcf-formula-sheet.md").write_bytes(human_note())
    return Writer(v, tmp_path / "journal.db")


def create(title="WACC notes", body="Cost of capital, weighted.", folder="Finance", **kw):
    return {"op": "create", "folder": folder, "title": title, "body": body, **kw}


def test_ulid_and_slug():
    assert ULID.match(new_ulid()) and new_ulid(0)[:10] == "0000000000"
    assert slugify("Café: DCF & WACC (v2)!") == "caf-dcf-wacc-v2" and slugify("!!!") == "note"


def test_proposing_writes_nothing(w):
    before = snapshot(w.vault.root)
    p = w.propose(AGENT, "add WACC", [create(), {"op": "update", "uid": HUMAN, "body": "rewritten"}])
    assert p["status"] == "pending" and snapshot(w.vault.root) == before          # I1
    assert [c["op"] for c in p["preview"]] == ["create", "update"]
    assert "+title: WACC notes" in p["preview"][0]["diff"] and "-My own words." in p["preview"][1]["diff"]


def test_approve_then_undo_is_byte_exact(w):
    before = snapshot(w.vault.root)
    p = w.propose(AGENT, "three changes", [create(), {"op": "update", "uid": HUMAN, "body": "Rewritten.\n", "tags": ["dcf"]}])
    batch = w.approve(p["id"])
    assert batch["status"] == "applied" and w.proposal(p["id"])["status"] == "applied"
    after = snapshot(w.vault.root)
    new = after["Finance/wacc-notes.md"].decode()
    note = parse_note("Finance/wacc-notes.md", new)[0]
    assert note.problems == [] and note.origin == "agent" and note.agent == AGENT
    dcf = after["Finance/dcf-formula-sheet.md"].decode()
    assert "Rewritten." in dcf and "custom_plugin_key: keep me" in dcf and "edited_by: ['claude:cs_test']" in dcf
    assert "origin: human" in dcf                                                 # provenance kept
    w.undo(batch["id"])
    assert snapshot(w.vault.root) == before                                       # I2, byte for byte
    assert w.batch(batch["id"])["status"] == "undone"
    with pytest.raises(ProposalError):
        w.undo(batch["id"])


def test_update_rewrites_only_the_keys_it_changes(w):
    path = w.vault.root / "Finance" / "dcf-formula-sheet.md"
    path.write_bytes(human_note(extra="# my comment\nlinks: [01J9ZQ4V6R8T2M3N5P7Q9S1W40]\nsource: 'Notebook p. 4'\naliases:\n  - DCF\n"))
    old = path.read_text(encoding="utf-8").splitlines()
    w.approve(w.propose(AGENT, "", [{"op": "update", "uid": HUMAN, "tags": ["dcf", "valuation"]}])["id"])
    new = path.read_text(encoding="utf-8").splitlines()
    assert set(old) - set(new) == {"updated: 2026-03-14"}                       # nothing else removed
    added = set(new) - set(old)
    assert "tags: [dcf, valuation]" in added and "edited_by: ['claude:cs_test']" in added and len(added) == 3
    assert new[-3:] == old[-3:]                                                   # body untouched


def test_edit_frontmatter_falls_back_when_unsure():
    from sage_os_hub.knowledge.proposals import edit_frontmatter
    import yaml
    raw = "title: A\n? complex key\n: value\n"                                    # not a simple key: value layout
    out = edit_frontmatter(raw, {"title": "B"})
    assert yaml.safe_load(out)["title"] == "B" and yaml.safe_load(out)["complex key"] == "value"


def test_archive_moves_and_undo_moves_back(w):
    before = snapshot(w.vault.root)
    b = w.approve(w.propose(AGENT, "", [{"op": "archive", "uid": HUMAN}])["id"])
    after = snapshot(w.vault.root)
    assert "Finance/dcf-formula-sheet.md" not in after and after["Archive/Finance/dcf-formula-sheet.md"] == human_note()
    w.undo(b["id"])
    assert snapshot(w.vault.root) == before


def test_stale_proposal_is_refused(w):
    p = w.propose(AGENT, "", [{"op": "update", "uid": HUMAN, "body": "agent text"}])
    path = w.vault.root / "Finance" / "dcf-formula-sheet.md"
    path.write_bytes(human_note(extra="tags: [mine]\n"))                           # the user edits meanwhile
    edited = snapshot(w.vault.root)
    with pytest.raises(StaleProposal):
        w.approve(p["id"])
    assert snapshot(w.vault.root) == edited and w.proposal(p["id"])["status"] == "pending"


def test_undo_refuses_to_overwrite_later_edits(w):
    b = w.approve(w.propose(AGENT, "", [create()])["id"])
    (w.vault.root / "Finance" / "wacc-notes.md").write_text("edited by hand", encoding="utf-8")
    with pytest.raises(ProposalError, match="overwrite edits"):
        w.undo(b["id"])
    assert (w.vault.root / "Finance" / "wacc-notes.md").read_text(encoding="utf-8") == "edited by hand"


def test_failure_midway_leaves_the_vault_untouched(w, monkeypatch):
    before = snapshot(w.vault.root)
    p = w.propose(AGENT, "", [create(), create("Second"), {"op": "update", "uid": HUMAN, "body": "x"}])
    real, calls = writer_module._put, []

    def flaky(path, data):
        calls.append(path)
        if len(calls) == 3:
            raise OSError("disk full")
        real(path, data)
    monkeypatch.setattr(writer_module, "_put", flaky)
    with pytest.raises(ProposalError, match="nothing was changed"):
        w.approve(p["id"])
    monkeypatch.setattr(writer_module, "_put", real)
    assert snapshot(w.vault.root) == before                                       # I9
    assert w.history()[0]["status"] == "rolled_back" and w.proposal(p["id"])["status"] == "pending"


def test_recover_rolls_back_a_crashed_batch(w, tmp_path):
    before = snapshot(w.vault.root)
    p = w.propose(AGENT, "", [create(), {"op": "update", "uid": HUMAN, "body": "half"}])
    from sage_os_hub.knowledge.proposals import plan
    entries = [e for x in plan(w.vault, p["changes"], AGENT) for e in x.entries]
    bid = w._journal(p["id"], AGENT, "", entries)                                 # journal written ...
    writer_module._put(w.vault.root / entries[0].path, entries[0].after)          # ... one file, then "crash"
    w.close()
    w2 = Writer(w.vault, tmp_path / "journal.db")
    assert w2.recover() == [bid] and snapshot(w.vault.root) == before
    assert w2.history()[0]["status"] == "rolled_back"


def test_bad_proposals_never_reach_the_inbox(w):
    (w.vault.root / "Finance" / "loose.md").write_text("no frontmatter", encoding="utf-8")
    bad = [
        ("", [create()]), (AGENT, []), (AGENT, [{"op": "delete", "uid": HUMAN}]),
        (AGENT, [create(folder="../outside")]), (AGENT, [create(folder="Archive")]), (AGENT, [create(folder="C:/x")]),
        (AGENT, [{"op": "create", "folder": "Finance", "body": "no title"}]),
        (AGENT, [{"op": "update", "uid": HUMAN}]), (AGENT, [{"op": "update", "uid": new_ulid(), "body": "x"}]),
        (AGENT, [create(links=["not-a-uid"])]), (AGENT, [create(title="two\nlines")]),
        (AGENT, [{"op": "update", "uid": HUMAN, "body": "a"}, {"op": "archive", "uid": HUMAN}]),
    ]
    for agent, changes in bad:
        with pytest.raises(ProposalError):
            w.propose(agent, "", changes)
    assert w.proposals() == []


def test_name_collisions_get_a_suffix(w):
    b = w.approve(w.propose(AGENT, "", [create("DCF formula sheet"), create("DCF formula sheet")])["id"])
    assert [f["path"] for f in b["files"]] == ["Finance/dcf-formula-sheet-2.md", "Finance/dcf-formula-sheet-3.md"]


def make(tmp_path):
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db",
                 vault_journal=tmp_path / "journal.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db", claude_workspaces=[str(tmp_path)], claude_enabled=False, hermes_profiles=[])
    return create_app(cfg, start_adapters=False)


def test_routes_inbox_approval_and_undo(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        vault = tmp_path / "vault"
        before = snapshot(vault)
        assert c.post("/api/vault/proposals", json={"agent": AGENT, "changes": [create()]}).status_code == 403
        assert c.post("/api/vault/proposals", json={"agent": AGENT, "changes": [create(folder="..")]}, headers=H).status_code == 400
        p = c.post("/api/vault/proposals", json={"agent": AGENT, "summary": "add WACC", "changes": [create()]}, headers=H).json()
        assert snapshot(vault) == before                                          # nothing until approved
        (item,) = [i for i in c.get("/api/state").json()["panels"]["inbox"] if i["source"] == "bookshelf"]
        assert item["choices"] == ["approve", "reject"] and item["context"]["changes"][0]["path"] == "Finance/wacc-notes.md"
        r = c.post(f"/api/inbox/{item['id']}", json={"choice": "approve"}, headers=H)
        assert r.status_code == 200 and (vault / "Finance" / "wacc-notes.md").exists()
        (batch,) = c.get("/api/vault/history").json()
        assert batch["proposal_id"] == p["id"] and batch["files"] == [{"path": "Finance/wacc-notes.md", "op": "create"}]
        assert c.post(f"/api/vault/batches/{batch['id']}/undo").status_code == 403
        assert c.post(f"/api/vault/batches/{batch['id']}/undo", headers=H).json()["status"] == "undone"
        assert snapshot(vault) == before
        assert c.post(f"/api/vault/batches/{batch['id']}/undo", headers=H).status_code == 409


def test_reject_and_pending_survive_a_restart(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        c.post("/api/vault/proposals", json={"agent": AGENT, "changes": [create()]}, headers=H)
        p2 = c.post("/api/vault/proposals", json={"agent": AGENT, "changes": [create("Other")]}, headers=H).json()
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:                 # hub restarted
        items = [i for i in c.get("/api/state").json()["panels"]["inbox"] if i["source"] == "bookshelf"]
        assert len(items) == 2
        it = next(i for i in items if i["context"]["proposal_id"] == p2["id"])
        c.post(f"/api/inbox/{it['id']}", json={"choice": "reject", "note": "not needed"}, headers=H)
        (rej,) = c.get("/api/vault/proposals", params={"status": "rejected"}).json()
        assert rej["note"] == "not needed" and not (tmp_path / "vault" / "Finance" / "other.md").exists()
