"""Bookshelf K2: FTS5 search over the vault -- ranked, stemmed, prefix-aware, a rebuildable cache."""
import random
import statistics
import time

from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.knowledge import SearchIndex, Vault
from sage_os_hub.knowledge.index import HIT_END, HIT_START, fts_query

N = iter(range(10**6))


def note(title, body, tags=(), folder="Notes", archived=False):
    i = next(N)
    uid = f"01J9ZQ4V6R8T2M3N5P7Q{i:06d}"
    tag_line = f"tags: [{', '.join(tags)}]\n" if tags else ""
    path = f"{'Archive' if archived else folder}/{title.lower().replace(' ', '-')}-{i}.md"
    return path, (f"---\nuid: {uid}\ntitle: {title}\ncreated: 2026-10-01\nupdated: 2026-10-01\ntype: note\n"
                  f"status: active\norigin: human\n{tag_line}---\n{body}\n")


def setup(tmp_path, notes):
    v = Vault(tmp_path / "vault")
    v.ensure()
    for rel, text in notes:
        p = v.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    idx = SearchIndex(tmp_path / "index.db")
    idx.sync(v.scan(), v.read_body)
    return v, idx


def titles(res):
    return [r["title"] for r in res["results"]]


def test_query_is_safe_and_prefix_aware():
    assert fts_query("  ") is None and fts_query('"); DROP TABLE docs; --') == '("drop" OR "drop"*) AND ("table" OR "table"*) AND ("docs" OR "docs"*)'
    assert fts_query("DCF val") == '("dcf" OR "dcf"*) AND ("val" OR "val"*)'


def test_ranking_stems_prefixes_and_snippets(tmp_path):
    _, idx = setup(tmp_path, [
        note("DCF formula sheet", "Enterprise value is the sum of discounted free cash flows.", ["finance", "valuation"]),
        note("Grocery list", "milk, eggs, bread. Remember the DCF homework later."),
        note("Valuation methods", "Comparables, precedent transactions and discounted cash flow."),
    ])
    assert titles(idx.search("dcf"))[0] == "DCF formula sheet"          # title outranks a body mention
    assert "Grocery list" in titles(idx.search("dcf"))
    assert set(titles(idx.search("valuing"))) == {"DCF formula sheet", "Valuation methods"}   # stem: tag + title
    assert titles(idx.search("discount"))                               # prefix of "discounted"
    assert idx.search("disc cash")["results"]                           # every word, as prefixes
    assert idx.search("blockchain")["results"] == []
    snip = idx.search("homework")["results"][0]["snippet"]
    assert f"{HIT_START}homework{HIT_END}" in snip


def test_archive_excluded_unless_asked(tmp_path):
    _, idx = setup(tmp_path, [note("Old study plan", "retired timetable", archived=True)])
    assert idx.search("timetable")["results"] == []
    assert titles(idx.search("timetable", archived=True)) == ["Old study plan"]


def test_sync_tracks_edits_and_deletes(tmp_path):
    v, idx = setup(tmp_path, [note("Alpha", "first words")])
    (path,) = [p for p in v.root.rglob("*.md")]
    path.write_text(path.read_text(encoding="utf-8").replace("first words", "second thoughts, now longer"), encoding="utf-8")
    assert idx.sync(v.scan(), v.read_body)["updated"] == 1
    assert idx.search("first")["results"] == [] and titles(idx.search("thoughts")) == ["Alpha"]
    path.unlink()
    assert idx.sync(v.scan(), v.read_body)["removed"] == 1 and idx.count() == 0
    s = idx.sync(v.scan(), v.read_body)                                 # nothing changed: nothing re-read
    assert (s["added"], s["updated"], s["removed"]) == (0, 0, 0)


def test_index_is_a_rebuildable_cache(tmp_path):
    v, idx = setup(tmp_path, [note("Alpha", "apples"), note("Beta", "bananas and apples")])
    before = idx.search("apples")["results"]
    idx.close()
    (tmp_path / "index.db").unlink()                                     # delete the cache from cold
    fresh = SearchIndex(tmp_path / "index.db")
    assert fresh.count() == 0
    fresh.rebuild(v.scan(), v.read_body)
    assert fresh.search("apples")["results"] == before


def test_gate_2000_notes_under_300ms(tmp_path):
    rng = random.Random(7)
    words = ("valuation cash flow discount equity debt budget category grocery rent transport tuition exam "
             "lecture notes python model agent kanban vault search index market bond yield inflation").split()
    notes = [note(" ".join(rng.sample(words, 3)).title(), " ".join(rng.choices(words, k=250)), rng.sample(words, 2))
             for _ in range(2000)]
    _, idx = setup(tmp_path, notes)
    assert idx.count() == 2000
    times = []
    for q in ["valuation", "cash fl", "budget grocery", "infl", "agent vault search", "zzz"]:
        t = time.perf_counter()
        idx.search(q)
        times.append((time.perf_counter() - t) * 1000)
    assert max(times) < 300, times
    assert statistics.median(times) < 100, times


def test_routes(tmp_path):
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db", vault_journal=tmp_path / "journal.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db",
                 claude_workspaces=[str(tmp_path)], claude_enabled=False, hermes_profiles=[])
    app = create_app(cfg, start_adapters=False)
    rel, text = note("DCF formula sheet", "discounted cash flows")
    (tmp_path / "vault" / "Notes").mkdir(parents=True)
    (tmp_path / "vault" / rel).write_text(text, encoding="utf-8")
    with TestClient(app, base_url="http://127.0.0.1") as c:
        res = c.get("/api/vault/search", params={"q": "cash"}).json()        # first search syncs on demand
        assert titles(res) == ["DCF formula sheet"] and res["results"][0]["ref"].startswith("01J9")
        assert c.post("/api/vault/reindex").status_code == 403
        r = c.post("/api/vault/reindex", headers={"x-sage-os": "1"}).json()
        assert r["added"] == 1 and r["indexed"] == 1
