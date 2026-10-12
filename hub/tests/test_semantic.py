"""K14 meaning-based search (D37): passages, the vector store, hybrid ranking, the indexer and briefing packs, with a
stand-in embedder (concept counts) so no model is needed."""
import asyncio
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.knowledge import semantic as sem
from sage_os_hub.knowledge.semantic import Semantic, VectorStore, chunks

from test_agent_tools import cfg

H = {"x-sage-os": "1"}
CONCEPTS = [
    {"present", "value", "discount", "discounting", "future", "cash", "flows", "worth", "today", "pv", "money"},
    {"inventory", "inventories", "lifo", "fifo", "stock", "goods", "warehouse"},
    {"revenue", "recognition", "recognise", "sales", "contract", "customer", "performance", "obligation"},
    {"golf", "course", "club", "swing", "tee"},
]


def fake_vec(text: str) -> np.ndarray:
    words = re.findall(r"[a-z]+", text.lower().split("|", 1)[-1])
    v = np.zeros(len(CONCEPTS) + 8, dtype=np.float32)
    for w in words:
        hits = [i for i, c in enumerate(CONCEPTS) if w in c]
        for i in hits:
            v[i] += 1
        if not hits:
            v[len(CONCEPTS) + hash(w) % 8] += 0.15             # other words: a little noise
    return v / max(np.linalg.norm(v), 1e-9)


class FakeEngine:
    serving = {"ready": True}
    proc = None
    jobs: dict = {}

    def installed(self):
        return True

    def stop(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(Semantic, "_post", lambda self, texts: np.vstack([fake_vec(t) for t in texts]))
    app = create_app(cfg(tmp_path, claude_enabled=False, hermes_profiles=[], engine_enabled=False), start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        hub = app.state.hub
        hub.semantic.engine = FakeEngine()
        yield hub, client


def run(hub, coro):
    return asyncio.run_coroutine_threadsafe(coro, hub.loop).result()


def file_notes(hub, notes):
    """Approve notes into the vault (folder Finance) and embed them."""
    changes = [{"op": "create", "folder": "Finance", "title": t, "body": b} for t, b in notes]
    p = run(hub, hub.submit_proposal("claude:s", "notes", changes))["proposal"]
    hub.writer.approve(p["id"])
    hub.index.sync(hub.vault.scan(), hub.vault.read_body)
    todo, gone = hub.semantic._note_work()
    run(hub, hub.semantic._embed_items("note", todo, "notes"))
    return todo


NOTES = [
    ("Present value", "The worth today of money received later, found by discounting future cash flows."),
    ("FIFO and LIFO", "Two cost-flow assumptions for inventory: first in first out, last in first out."),
    ("Club calendar", "The golf club meets at the course on Tuesdays for swing and tee practice; golf members "
                      "value the club course and its cash prizes for the best tee shot at the golf course."),
    # wordy look-alike: shares 'value' and 'cash' with a present-value question but is about golf
]


# -- pieces ------------------------------------------------------------------------------------------------------
def test_chunks_cover_the_text_with_overlap():
    text = ("Sentence number %d is here. " * 400) % tuple(range(400))
    parts = chunks(text)
    assert len(parts) > 5 and parts[0][0] == 0
    assert all(len(p) <= sem.CHUNK for _, p in parts)
    covered = set()
    for off, p in parts:
        start = text.index(p[:40], max(0, off - 5))
        covered.update(range(start, start + len(p)))
    assert len(covered) >= len(text.strip()) - 5                     # nothing skipped
    assert chunks("") == [] and chunks("short") == [(0, "short")]


def test_store_nearest_best_passage_per_document_and_model_change(tmp_path):
    s = VectorStore(tmp_path / "v.db")
    s.set_model("m1")
    a, b = fake_vec("present value"), fake_vec("inventory lifo")
    s.put("source", "drive/a.pdf", [{"chunk": 0, "hash": "h"}, {"chunk": 1, "hash": "h"}], np.vstack([b, a]))
    s.put("source", "drive/b.pdf", [{"chunk": 0, "hash": "h2"}], np.vstack([b]))
    hits = s.nearest("source", fake_vec("discount future cash"), 5)
    assert [m["ref"] for _, m in hits] == ["drive/a.pdf", "drive/b.pdf"] and hits[0][1]["chunk"] == 1
    assert s.hashes("source") == {"drive/a.pdf": "h", "drive/b.pdf": "h2"} and s.count("source") == 2
    s.delete("source", ["drive/b.pdf"])
    assert s.count("source") == 1
    s.set_model("m2")                                                     # other model: vectors can't be compared
    assert s.count("source") == 0


def test_fuse_keeps_words_adds_meaning_and_ignores_far_meaning():
    kw = [{"ref": "A", "title": "a"}, {"ref": "B", "title": "b"}]
    meaning = [(0.9, {"ref": "C"}), (0.8, {"ref": "A"}), (0.1, {"ref": "D"})]
    out = Semantic.fuse(kw, meaning, "ref", 10)
    by = {r.get("ref") or r["_meta"]["ref"]: r for r in out}
    assert by["A"]["match"] == "both" and by["B"]["match"] == "words" and by["C"]["match"] == "meaning"
    assert "D" not in by and out[0]["ref"] == "A"                         # both lists agree on A: it ranks first


# -- search ------------------------------------------------------------------------------------------------------
def test_a_differently_worded_question_finds_the_note(env):
    hub, client = env
    file_notes(hub, NOTES)
    words = hub.index.search("how much is money received later worth now")["results"]
    assert not any(r["title"] == "Present value" for r in words)          # keyword search misses it
    r = client.get("/api/vault/search", params={"q": "discount future cash flows to today"}).json()
    assert r["mode"] == "both"
    top = r["results"][0]
    assert top["title"] == "Present value" and top["match"] in ("meaning", "both")
    r = client.get("/api/vault/search", params={"q": "how much is money received later worth now"}).json()
    assert r["results"][0]["title"] == "Present value" and r["results"][0]["match"] == "meaning"
    assert r["results"][0]["snippet"].startswith("The worth today")


def test_search_falls_back_to_words_without_the_model(env):
    hub, client = env
    file_notes(hub, NOTES)
    hub.semantic.engine.serving = {"ready": False}
    r = client.get("/api/vault/search", params={"q": "inventory"}).json()
    assert r["mode"] == "words" and r["results"][0]["title"] == "FIFO and LIFO"
    hub.semantic.engine.serving = {"ready": True}


def test_indexer_re_embeds_only_changed_notes_and_forgets_removed_ones(env):
    hub, client = env
    file_notes(hub, NOTES)
    todo, gone = hub.semantic._note_work()
    assert todo == [] and gone == []
    n = next(x for x in hub.vault.scan() if x.title == "FIFO and LIFO")
    (hub.vault.root / n.path).write_text((hub.vault.root / n.path).read_text(encoding="utf-8") + "\nWeighted average too.\n",
                                         encoding="utf-8")
    todo, gone = hub.semantic._note_work()
    assert [t[0] for t in todo] == [n.ref]
    (hub.vault.root / n.path).unlink()
    todo, gone = hub.semantic._note_work()
    assert todo == [] and gone == [n.ref]


def test_sensitive_notes_are_embedded_by_title_only(env):
    hub, client = env
    file_notes(hub, [("Bank", "Account details for the trust fund and its present value.")])
    n = hub.vault.scan()[0]
    n.sensitive = "an account number"
    hub.vault.scan = lambda: [n]
    todo, _ = hub.semantic._note_work()
    assert todo[0][2] == ["title: Bank | text: Bank"] and todo[0][1][0]["preview"] == ""


def test_source_passages_are_indexed_a_few_documents_at_a_time(env, monkeypatch):
    hub, client = env
    docs = {("drive", f"doc{i}.pdf"): f"{i}:1:5000" for i in range(8)}
    monkeypatch.setattr(hub.sources, "fingerprints", lambda: docs)
    monkeypatch.setattr(hub.sources, "full_text", lambda s, r: "Inventory valuation with LIFO. " * 100)
    todo, gone, waiting = hub.semantic._source_work()
    assert len(todo) == 5 and waiting == 8 and all(len(t[2]) >= 2 for t in todo)
    run(hub, hub.semantic._embed_items("source", todo, "documents"))
    todo, gone, waiting = hub.semantic._source_work()
    assert len(todo) == 3 and waiting == 3


# -- briefing packs ---------------------------------------------------------------------------------------------
def test_briefing_pack_keeps_the_paraphrase_and_drops_the_wordy_look_alike(env):
    hub, client = env
    file_notes(hub, NOTES)
    _, items = hub.briefings.pick("What is the present value of cash I get in five years?", set())
    titles = [i.title for i in items]
    assert "Present value" in titles and "Club calendar" not in titles
    hub.semantic.engine.serving = {"ready": False}                   # words only still briefs
    _, items = hub.briefings.pick("What is the present value of cash I get in five years?", set())
    assert "Present value" in [i.title for i in items]
    hub.semantic.engine.serving = {"ready": True}


def test_briefing_pack_finds_a_note_that_shares_no_words(env):
    hub, client = env
    file_notes(hub, NOTES)
    _, items = hub.briefings.pick("Which stock goods method assumes the warehouse ships the oldest first?", set())
    assert [i.title for i in items][:1] == ["FIFO and LIFO"]


# -- status and download -----------------------------------------------------------------------------------------
def test_status_and_download_route(env):
    hub, client = env
    assert client.get("/api/semantic").json()["installed"] is True
    assert client.post("/api/semantic/download").status_code == 403                     # write header needed
    hub.semantic.engine = None
    assert client.post("/api/semantic/download", headers=H).status_code == 409


def test_sentences_lean_on_meaning_and_short_terms_on_words():
    assert sem.lean("LIFO reserve") == 1.0 and sem.lean("own the shares and buy the right to sell") == 2.0
    kw = [{"ref": "junk", "title": "j"}]
    meaning = [(0.5, {"ref": "answer"})]
    assert Semantic.fuse(kw, meaning, "ref", 5, lean=2.0)[0]["_meta"]["ref"] == "answer"
    assert Semantic.fuse(kw, meaning, "ref", 5, lean=1.0)[0]["ref"] == "junk"          # a tie keeps words first
