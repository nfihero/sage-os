"""K13 review: keep some notes of a proposal, edit some, file only those; undo stays exact."""
import asyncio
import hashlib

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.knowledge.proposals import ProposalError, apply_review

from test_agent_tools import cfg

H = {"x-sage-os": "1"}
CHANGES = [{"op": "create", "folder": "Books/Kieso", "title": f"Note {i}", "body": f"Body {i}.", "tags": ["acc"]} for i in range(4)]


@pytest.fixture
def env(tmp_path):
    app = create_app(cfg(tmp_path, claude_enabled=False, hermes_profiles=[], engine_enabled=False), start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        hub = app.state.hub
        r = asyncio.run_coroutine_threadsafe(hub.submit_proposal("digest:m", "Chapter 1", CHANGES), hub.loop).result()
        yield hub, client, r["proposal"]["id"]


def fingerprint(root):
    return sorted((p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob("*.md"))


def card(hub, pid):
    return next(i for i in hub.inbox.items() if i["context"].get("proposal_id") == pid)


def test_apply_review_validates():
    norm = [dict(c, uid=f"01J9ZQ4V6R8T2M3N5P7Q9S1W5{i}") for i, c in enumerate(CHANGES)]
    out, s = apply_review(norm, [0, 2], {"2": {"body": "Better body."}})
    assert [c["title"] for c in out] == ["Note 0", "Note 2"] and out[1]["body"] == "Better body."
    assert out[1]["edited_by"] == ["user"] and "edited_by" not in out[0] and s == {"kept": 2, "dropped": 2, "edited": [2]}
    with pytest.raises(ProposalError):
        apply_review(norm, [9], {})
    with pytest.raises(ProposalError):
        apply_review(norm, [0], {"0": {"folder": "Elsewhere"}})
    with pytest.raises(ProposalError):
        apply_review(norm, [0], {"0": {"title": "two\nlines"}})
    unchanged, s = apply_review(norm, [0], {"0": {"title": "Note 0"}})      # an "edit" that changes nothing
    assert "edited_by" not in unchanged[0] and s["edited"] == []


def test_review_files_only_kept_notes_with_edits_and_undo_is_exact(env):
    hub, client, pid = env
    before = fingerprint(hub.vault.root)
    full = client.get(f"/api/vault/proposals/{pid}").json()
    assert [c["title"] for c in full["changes"]] == ["Note 0", "Note 1", "Note 2", "Note 3"] and full["changes"][0]["body"] == "Body 0."
    r = client.post(f"/api/inbox/{card(hub, pid)['id']}", headers=H, json={
        "choice": "approve", "review": {"keep": [0, 1, 3], "edits": {"1": {"title": "Note one, edited", "body": "## Mine\n\nRewritten."}}}})
    assert r.status_code == 200, r.text
    files = {p.name: p.read_text(encoding="utf-8") for p in hub.vault.root.rglob("*.md")}
    assert "note-2.md" not in files and {"note-0.md", "note-one-edited.md", "note-3.md"} <= set(files)
    edited = files["note-one-edited.md"]
    assert "Rewritten." in edited and "edited_by:" in edited and "user" in edited and "agent: digest:m" in edited
    assert "edited_by" not in files["note-0.md"]
    p = hub.writer.proposal(pid)
    assert p["status"] == "applied" and len(p["changes"]) == 3
    with hub.writer.lock:
        original, review = hub.writer.db.execute("SELECT original, review FROM proposals WHERE id=?", (pid,)).fetchone()
    assert '"Note 2"' in original and '"dropped": 1' in review                # the agent's version is kept
    batch = hub.writer.history(1)[0]
    hub.writer.undo(batch["id"])
    assert fingerprint(hub.vault.root) == before


def test_review_needs_something_kept_and_screens_edits(env):
    hub, client, pid = env
    cid = card(hub, pid)["id"]
    r = client.post(f"/api/inbox/{cid}", headers=H, json={"choice": "approve", "review": {"keep": [], "edits": {}}})
    assert r.status_code >= 400 and "nothing kept" in r.text
    assert hub.writer.proposal(pid)["status"] == "pending"
    r = client.post(f"/api/inbox/{cid}", headers=H, json={"choice": "approve", "review": {"keep": [0], "edits": {"0": {"body": "password: Xk29fjq0LmP"}}}})
    assert r.status_code >= 400 and "Xk29" not in r.text
    assert hub.writer.proposal(pid)["status"] == "pending" and not list(hub.vault.root.rglob("note-0.md"))


def test_review_only_with_approve(env):
    hub, client, pid = env
    r = client.post(f"/api/inbox/{card(hub, pid)['id']}", headers=H, json={"choice": "reject", "review": {"keep": [0]}})
    assert r.status_code == 400
    assert client.post(f"/api/inbox/{card(hub, pid)['id']}", json={"choice": "approve", "review": {"keep": [0]}}).status_code == 403
