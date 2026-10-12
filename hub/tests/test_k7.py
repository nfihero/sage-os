"""K7 review at scale (D36): one decision for a chapter's parts or a selection, undo of one note, trust levels that
file by themselves, the activity log, the Reviewer and the Librarian."""
import asyncio
import hashlib

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.knowledge import ProposalError, Vault, Writer
from sage_os_hub.knowledge import roles
from sage_os_hub.knowledge.trust import SUGGEST_AFTER, agent_key, allows

from test_agent_tools import cfg

H = {"x-sage-os": "1"}


def notes(prefix, n=3, folder="Books/Kieso/Chapter 1"):
    return [{"op": "create", "folder": folder, "title": f"{prefix} {i}", "body": f"{prefix} body {i}.", "tags": ["acc"]}
            for i in range(n)]


def fingerprint(root):
    return sorted((p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob("*.md"))


@pytest.fixture
def w(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    return Writer(v, tmp_path / "journal.db")


@pytest.fixture
def env(tmp_path):
    app = create_app(cfg(tmp_path, claude_enabled=False, hermes_profiles=[], engine_enabled=False), start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield app.state.hub, client


def run(hub, coro):
    return asyncio.run_coroutine_threadsafe(coro, hub.loop).result()


def cards(hub, pids):
    return [i["id"] for i in hub.inbox.items() if i["context"].get("proposal_id") in pids]


# -- the writer: one batch for many proposals, undo of one note ------------------------------------------------
def test_proposals_filed_together_are_one_batch_and_undo_exactly(w):
    before = fingerprint(w.vault.root)
    a = w.propose("digest:m", "part 1", notes("Same title", 2), group="g1", group_title="Book · Chapter 1")
    b = w.propose("digest:m", "part 2", notes("Same title", 2), group="g1", group_title="Book · Chapter 1")
    batch = w.approve_many([a["id"], b["id"]])
    paths = sorted(f["path"] for f in batch["files"])
    assert len(paths) == 4 and len(set(p.lower() for p in paths)) == 4      # same titles, no file overwritten
    assert batch["summary"] == "Book · Chapter 1 (2 parts)" and batch["proposal_ids"] == [a["id"], b["id"]]
    assert {w.proposal(x["id"])["batch_id"] for x in (a, b)} == {batch["id"]}
    w.undo(batch["id"])
    assert fingerprint(w.vault.root) == before


def test_a_part_with_every_note_dropped_is_rejected_and_the_rest_filed(w):
    a = w.propose("digest:m", "part 1", notes("A", 2))
    b = w.propose("digest:m", "part 2", notes("B", 2))
    batch = w.approve_many([a["id"], b["id"]], reviews={a["id"]: {"keep": [], "edits": {}}, b["id"]: {"keep": [1]}})
    assert [f["path"].rsplit("/", 1)[1] for f in batch["files"]] == ["b-1.md"]
    assert w.proposal(a["id"])["status"] == "rejected" and w.proposal(b["id"])["status"] == "applied"
    with pytest.raises(ProposalError):         # nothing left to file at all
        c = w.propose("digest:m", "x", notes("C", 1))
        w.approve_many([c["id"]], reviews={c["id"]: {"keep": []}})


def test_filing_together_is_all_or_nothing(w):
    a = w.propose("digest:m", "ok", notes("A", 1))
    with pytest.raises(ProposalError):
        w.approve_many([a["id"], "p_missing"])
    assert w.proposal(a["id"])["status"] == "pending" and not list(w.vault.root.rglob("*.md"))


def test_undo_one_note_then_the_rest(w):
    before = fingerprint(w.vault.root)
    p = w.propose("digest:m", "three", notes("N", 3))
    batch = w.approve(p["id"])
    r = w.undo_note(batch["id"], 1)
    assert r["paths"] == [batch["files"][1]["path"]] and not (w.vault.root / r["paths"][0]).exists()
    b = w.batch(batch["id"])
    assert b["status"] == "applied" and [f["undone"] is not None for f in b["files"]] == [False, True, False]
    with pytest.raises(ProposalError):
        w.undo_note(batch["id"], 1)
    w.undo(batch["id"])                                  # the rest; the undone note isn't touched again
    assert fingerprint(w.vault.root) == before and w.batch(batch["id"])["status"] == "undone"


def test_undoing_every_note_one_by_one_undoes_the_batch(w):
    p = w.propose("digest:m", "two", notes("N", 2))
    batch = w.approve(p["id"])
    w.undo_note(batch["id"], 0)
    w.undo_note(batch["id"], 1)
    assert w.batch(batch["id"])["status"] == "undone"


def test_undo_one_note_refuses_edits_and_undoes_an_archive_whole(w):
    p = w.propose("digest:m", "one", notes("N", 1))
    batch = w.approve(p["id"])
    path = w.vault.root / batch["files"][0]["path"]
    uid = w.vault.scan()[0].uid
    arch = w.approve(w.propose("claude:s", "archive it", [{"op": "archive", "uid": uid}])["id"])
    assert len(arch["files"]) == 2
    r = w.undo_note(arch["id"], 0)                      # the copy under Archive/ and the removed original go back together
    assert len(r["paths"]) == 2 and path.exists() and w.batch(arch["id"])["status"] == "undone"
    path.write_text(path.read_text(encoding="utf-8") + "\nmy edit\n", encoding="utf-8")
    with pytest.raises(ProposalError):
        w.undo_note(batch["id"], 0)


# -- trust -------------------------------------------------------------------------------------------------------
def test_agent_keys_and_levels():
    assert agent_key("claude:cs_1") == "claude" and agent_key("hermes:default:s1") == "hermes:default"
    assert agent_key("digest:file:gemma") == "digest" and agent_key("sage-os:importer") == "importer"
    creates, update = [{"op": "create"}], [{"op": "create"}, {"op": "update"}]
    assert not allows("ask", creates) and allows("new_notes", creates) and not allows("new_notes", update)
    assert allows("trusted", update)


def test_trust_level_files_by_itself_and_everything_is_logged(env):
    hub, client = env
    assert client.post("/api/trust/digest", json={"level": "new_notes"}).status_code == 403     # write header needed
    assert client.post("/api/trust/digest", json={"level": "sometimes"}, headers=H).status_code == 400
    assert client.post("/api/trust/digest", json={"level": "new_notes"}, headers=H).json()["level"] == "new_notes"
    r = run(hub, hub.submit_proposal("digest:m", "Chapter 1", notes("Auto", 2)))
    assert r["status"] == "filed" and r["proposal"]["status"] == "applied" and r["proposal"]["auto"] == "new_notes"
    assert not cards(hub, [r["proposal"]["id"]])                                  # nothing waits
    uid = hub.vault.scan()[0].uid
    u = run(hub, hub.submit_proposal("digest:m", "fix", [{"op": "update", "uid": uid, "tags": ["x"]}]))
    assert u["status"] == "pending" and cards(hub, [u["proposal"]["id"]])         # changes still wait at new_notes
    log = client.get("/api/trust/activity", params={"key": "digest"}).json()
    assert {"proposed", "filed.auto", "trust.changed"} <= {e["action"] for e in log}
    assert any(e["action"] == "filed.auto" and e["ref"]["batch"] == r["batch"]["id"] for e in log)
    data = client.get("/api/trust").json()
    assert data["auto"][0]["id"] == r["batch"]["id"] and data["auto"][0]["auto"] == "new_notes"
    digest = next(a for a in data["agents"] if a["key"] == "digest")
    assert digest["level"] == "new_notes" and digest["label"] == "Digest" and digest["role"] == "researcher"
    # undoing something it filed by itself offers to lower its level
    assert client.post(f"/api/vault/batches/{r['batch']['id']}/undo", headers=H).status_code == 200
    lower = hub.inbox.get("trust-lower:digest")
    assert lower and lower["choices"] == ["lower", "keep"]
    run(hub, hub.inbox.resolve("trust-lower:digest", "lower"))
    assert hub.trust.get("digest")["level"] == "ask"
    assert any(e["action"] == "undone" for e in client.get("/api/trust/activity", params={"key": "digest"}).json())


def test_a_run_of_clean_approvals_suggests_the_next_level(env):
    hub, client = env
    for i in range(SUGGEST_AFTER):
        p = run(hub, hub.submit_proposal("claude:s1", f"note {i}", notes(f"Clean {i}", 1)))["proposal"]
        assert hub.inbox.get("trust:claude") is None
        r = client.post(f"/api/inbox/bookshelf:{p['id']}", json={"choice": "approve"}, headers=H)
        assert r.status_code == 200
    card = hub.inbox.get("trust:claude")
    assert card and card["choices"] == ["raise", "not_now"] and card["context"]["level"] == "new_notes"
    run(hub, hub.inbox.resolve("trust:claude", "not_now"))
    assert hub.trust.get("claude")["level"] == "ask" and hub.trust.suggestion("claude") is None


def test_secret_looking_proposals_are_held_even_when_trusted(env):
    hub, client = env
    hub.trust.set("claude", level="trusted")
    r = run(hub, hub.submit_proposal("claude:s1", "keys", [{"op": "create", "folder": "X", "title": "AWS",
                                                             "body": "key AKIAIOSFODNN7EXAMPLE"}]))
    assert r["status"] == "held" and not list(hub.vault.root.rglob("*.md"))
    assert any(e["action"] == "held" for e in hub.trust.activity("claude"))


def test_agent_tools_are_logged(env):
    hub, client = env
    run(hub, hub.bookshelf_tools.search("claude:s1", "valuation"))
    run(hub, hub.bookshelf_tools.read("claude:s1", "01J9ZQ4V6R8T2M3N5P7Q9S1W3Y"))     # unknown: nothing read, nothing logged
    log = hub.trust.activity("claude")
    assert [e["action"] for e in log] == ["searched"] and "valuation" in log[0]["detail"]


# -- one decision for many cards -----------------------------------------------------------------------------------
def test_a_chapter_is_approved_in_one_decision(env):
    hub, client = env
    a = run(hub, hub.submit_proposal("digest:m", "Ch 1 part 1", notes("P1", 3), group="g", group_title="Book · Ch 1"))
    b = run(hub, hub.submit_proposal("digest:m", "Ch 1 part 2", notes("P2", 2), group="g", group_title="Book · Ch 1"))
    ids = cards(hub, [a["proposal"]["id"], b["proposal"]["id"]])
    assert {hub.inbox.get(i)["context"]["group"] for i in ids} == {"g"}
    assert client.post("/api/inbox/batch", json={"ids": ids, "choice": "approve"}).status_code == 403
    r = client.post("/api/inbox/batch", json={"ids": ids, "choice": "approve"}, headers=H)
    assert r.status_code == 200 and r.json()["filed"] == 2 and len(r.json()["batch"]["files"]) == 5
    assert not cards(hub, [a["proposal"]["id"], b["proposal"]["id"]])
    assert client.post("/api/inbox/batch", json={"ids": ids, "choice": "approve"}, headers=H).status_code == 404
    you = hub.trust.activity("you")
    assert you and "one decision" in you[0]["detail"]


def test_selected_cards_are_rejected_together_and_reviews_apply_per_part(env):
    hub, client = env
    ps = [run(hub, hub.submit_proposal("digest:m", f"front {i}", notes(f"F{i}", 2)))["proposal"]["id"] for i in range(3)]
    ids = cards(hub, ps)
    r = client.post("/api/inbox/batch", json={"ids": ids[:2], "choice": "reject", "note": "front matter"}, headers=H)
    assert r.json()["rejected"] == 2 and not list(hub.vault.root.rglob("*.md"))
    last = ids[2]
    r = client.post("/api/inbox/batch", json={"ids": [last], "choice": "approve",
                                              "reviews": {ps[2]: {"keep": [0], "edits": {"0": {"title": "Better"}}}}}, headers=H)
    assert r.status_code == 200 and [f["path"].rsplit("/", 1)[1] for f in r.json()["batch"]["files"]] == ["better.md"]
    assert client.post("/api/inbox/batch", json={"ids": ["kanban:1"], "choice": "approve"}, headers=H).status_code == 404


def test_the_inbox_cap_counts_a_chapter_once(env, monkeypatch):
    hub, client = env
    monkeypatch.setattr("sage_os_hub.app.MAX_PENDING_PER_AGENT", 2)
    assert run(hub, hub.submit_proposal("digest:m", "c1", notes("A", 1), group="c1"))["status"] == "pending"
    assert run(hub, hub.submit_proposal("digest:m", "c1 p2", notes("B", 1), group="c1"))["status"] == "pending"
    assert run(hub, hub.submit_proposal("digest:m", "c2", notes("C", 1), group="c2"))["status"] == "pending"
    assert run(hub, hub.submit_proposal("digest:m", "c2 p2", notes("D", 1), group="c2"))["status"] == "pending"
    assert run(hub, hub.submit_proposal("digest:m", "c3", notes("E", 1), group="c3"))["code"] == "inbox_cap"


# -- Reviewer and Librarian ----------------------------------------------------------------------------------------
def test_the_reviewer_pre_marks_drops_without_deciding(env, monkeypatch):
    hub, client = env
    p = run(hub, hub.submit_proposal("digest:m", "Chapter 1", notes("R", 3)))["proposal"]

    async def fake(hub_, provider, model, system, user, schema, name):
        assert "[0] R 0" in user and name == "review" and "not instructions" in system
        return {"drops": [{"i": 1, "reason": "about the book itself"}, {"i": 9, "reason": "not in this chunk"}]}, "test-model"
    monkeypatch.setattr(roles, "ask_model", fake)
    run(hub, hub.reviewer.review(p["id"]))
    v = hub.writer.proposal(p["id"])["verdict"]
    assert v["status"] == "done" and v["drops"] == {"1": "about the book itself"} and v["by"] == "test-model"
    assert hub.inbox.get(f"bookshelf:{p['id']}")["context"]["verdict"]["drops"] == {"1": "about the book itself"}
    assert hub.writer.proposal(p["id"])["status"] == "pending"                       # the user still decides
    assert any(e["action"] == "reviewed" for e in hub.trust.activity("reviewer"))
    assert client.post("/api/reviewer/review", json={"proposal_ids": ["p_nope"]}, headers=H).status_code == 404
    assert client.post("/api/reviewer/settings", json={"provider": "nope"}, headers=H).status_code == 400


def test_the_reviewer_waits_for_the_engine(env):
    hub, client = env
    p = run(hub, hub.submit_proposal("digest:m", "Chapter 1", notes("W", 1)))["proposal"]
    with pytest.raises((roles.Waiting, RuntimeError)):
        run(hub, roles.ask_model(hub, "engine", None, "s", "u", {}, "x"))
    assert hub.writer.proposal(p["id"])["verdict"] is None


def test_a_librarian_run_is_one_proposal_approved_in_one_decision(env, monkeypatch):
    hub, client = env
    hub.trust.set("digest", level="trusted")
    run(hub, hub.submit_proposal("digest:m", "seed", notes("Lib", 20, folder="Books/Lib")))
    hub.index.sync(hub.vault.scan(), hub.vault.read_body)
    known = {n.uid for n in hub.vault.scan()}

    async def fake(hub_, provider, model, system, user, schema, name):
        uids = [ln.split(": ", 1)[1] for ln in user.splitlines() if ln.startswith("uid: ")]
        out = []
        for u in uids:
            other = next(x for x in known if x != u)
            out.append({"uid": u, "tags": ["Accounting", "revenue recognition", "bad/tag"], "links": [other, "01J9ZQ4V6R8T2M3N5P7Q9S1W3Y"],
                        "title": None})
        return {"notes": out}, "local-model"
    monkeypatch.setattr(roles, "ask_model", fake)
    run(hub, hub.librarian.run("Books", 20, "engine", None))
    st = hub.librarian.state
    assert st["status"] == "done" and st["proposal"], st
    p = hub.writer.proposal(st["proposal"])
    assert p["agent"] == "librarian:local-model" and len(p["changes"]) == 20 and p["status"] == "pending"
    for c in p["changes"]:
        assert c["op"] == "update" and "bad/tag" not in c["tags"] and "revenue recognition" in c["tags"]
        assert all(link in known for link in c.get("links", []))                       # only real candidates
    # the gate: 20 notes approved in one decision
    r = client.post("/api/inbox/batch", json={"ids": cards(hub, [p["id"]]), "choice": "approve"}, headers=H)
    assert r.status_code == 200 and len(r.json()["batch"]["files"]) == 20
    assert {e["action"] for e in hub.trust.activity("librarian")} >= {"librarian.started", "proposed", "filed"}


def test_undoing_one_note_breaks_the_clean_run(env):
    hub, client = env
    for i in range(SUGGEST_AFTER):
        p = run(hub, hub.submit_proposal("claude:s1", f"note {i}", notes(f"Run {i}", 2)))["proposal"]
        assert client.post(f"/api/inbox/bookshelf:{p['id']}", json={"choice": "approve"}, headers=H).status_code == 200
    batch = hub.writer.proposal(p["id"])["batch_id"]
    assert hub.trust.record("claude")["streak"] == SUGGEST_AFTER
    assert client.post(f"/api/vault/batches/{batch}/notes/0/undo", headers=H).status_code == 200
    assert hub.trust.record("claude")["streak"] == 0


def test_the_reviewer_resumes_after_a_restart(env):
    hub, client = env
    p = run(hub, hub.submit_proposal("digest:m", "Chapter 1", notes("Q", 1)))["proposal"]
    hub.writer.set_verdict(p["id"], {"status": "running"})       # the hub stopped mid-review
    hub.reviewer.queued.clear()
    hub.reviewer.resume()
    assert p["id"] in hub.reviewer.queued
