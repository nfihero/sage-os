"""K12 (D23): long documents split into sections that tile the text, drafted section by section, checked
for concept coverage, proposed one chapter per inbox card."""
import asyncio
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.knowledge import digest as dg
from sage_os_hub.knowledge.digest import covered, parse_json
from sage_os_hub.knowledge.sections import check_tiling, heading, split_document, tile
from sage_os_hub.knowledge.sources import extract_text

from test_agent_tools import cfg

H = {"x-sage-os": "1"}


def book(chapters=3, sections=3, words=400) -> str:
    out = ["Copyright page. All rights reserved.\n"]
    for c in range(1, chapters + 1):
        out.append(f"\n# Chapter {c}: Topic {c}\n\n")
        for s in range(1, sections + 1):
            out.append(f"\n## {c}.{s} Concept C{c}S{s}\n\n")
            out.append(" ".join(f"Term{c}x{s} explains valuation step {i}." for i in range(words // 5)) + "\n")
    return "".join(out)


def test_headings_detected():
    assert heading("# Chapter 1: Money") == (1, "Chapter 1: Money")
    assert heading("CHAPTER 7 Risk and Return")[0] == 1
    assert heading("3.2 Present value of annuities") == (2, "3.2 Present value of annuities")
    assert heading("COST OF CAPITAL")[0] == 2
    assert heading("This is a normal sentence that ends with a period.") is None


def test_sections_tile_the_whole_text_and_follow_chapters():
    text = book()
    secs = tile(text, [(m.start(), len(m.group(1)), m.group(2)) for m in re.finditer(r"(?m)^(#{1,2}) (.+)$", text)], "Book")
    check_tiling(secs, len(text))                          # nothing falls between sections
    assert "".join(text[s.start:s.end] for s in secs) == text
    assert {s.chapter for s in secs} >= {"Chapter 1: Topic 1", "Chapter 3: Topic 3"}
    assert all(s.end - s.start <= 12_000 for s in secs)


def test_huge_section_split_at_paragraphs_and_tiny_ones_merged():
    big = "\n\n".join("Paragraph " + "word " * 300 for _ in range(60))      # ~110k chars, no headings
    secs = tile(big, [], "Notes")
    check_tiling(secs, len(big))
    assert len(secs) > 8 and all(s.end - s.start <= 13_000 for s in secs)
    small = "# A\nx\n# B\ny\n# C\n" + "z " * 2000
    secs = tile(small, [(0, 1, "A"), (5, 1, "B"), (10, 1, "C")], "Doc")
    check_tiling(secs, len(small))
    assert len(secs) == 1


def test_markdown_document_split(tmp_path):
    p = tmp_path / "book.md"
    p.write_text(book(), encoding="utf-8")
    text, secs = split_document(p, extract_text(p), "Book")
    check_tiling(secs, len(text))
    assert len({s.chapter for s in secs}) == 3


def test_epub_and_word_headings_become_markdown(tmp_path):
    import zipfile
    e = tmp_path / "b.epub"
    with zipfile.ZipFile(e, "w") as z:
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
        z.writestr("OEBPS/c.opf", '<package><manifest><item id="a" href="ch1.xhtml"/><item id="b" href="ch2.xhtml"/></manifest>'
                                  '<spine><itemref idref="b"/><itemref idref="a"/></spine></package>')
        z.writestr("OEBPS/ch1.xhtml", "<html><body><h1>Second</h1><p>two</p></body></html>")
        z.writestr("OEBPS/ch2.xhtml", "<html><body><h1>First</h1><p>one</p></body></html>")
    t = extract_text(e)
    assert t.index("# First") < t.index("# Second")        # spine order, headings kept
    d = tmp_path / "w.docx"
    with zipfile.ZipFile(d, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Intro</w:t></w:r></w:p>'
                                        "<w:p><w:r><w:t>Body text.</w:t></w:r></w:p></w:body></w:document>")
    assert "# Intro" in extract_text(d)


def test_parse_and_coverage():
    reply = '```json\n{"concepts": ["Net present value", "Discount rate"], "notes": [{"title": "NPV", "body": "Net present value sums discounted cash flows.", "covers": ["Net present value"]}]}\n```'
    data = parse_json(reply)
    assert covered(data["concepts"], data["notes"]) == ["Net present value"]
    with pytest.raises(ValueError):
        parse_json("no json here")


# -- the worker, end to end with a fake model --------------------------------------------------------
@pytest.fixture
def env(tmp_path, monkeypatch):
    c = cfg(tmp_path, claude_enabled=False, hermes_profiles=[], engine_root=tmp_path / "engine",
            sources=[{"name": "drive", "path": str(tmp_path / "G")}])
    (tmp_path / "G").mkdir()
    (tmp_path / "G" / "finance-book.md").write_text(book(chapters=2, sections=2, words=800), encoding="utf-8")
    app = create_app(c, start_adapters=False)
    hub = app.state.hub
    calls = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        calls.append(body)
        prompt = body["messages"][-1]["content"]
        if "aren't covered" in prompt:                     # follow-up: cover the missing concept
            missing = json.loads(prompt.split("yet: ")[1].split(". Write")[0])
            notes = [{"title": f"About {m}", "body": f"{m} is covered here.", "covers": [m]} for m in missing]
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"concepts": missing, "notes": notes})}}]})
        sec = re.search(r'Section: "([^"]+)"', prompt).group(1)
        if "Copyright" in prompt and "Concept" not in prompt:
            content = {"concepts": [], "notes": []}
        else:
            content = {"concepts": [f"Idea of {sec}", "Hidden extra"],
                       "notes": [{"title": f"Note on {sec}", "body": f"Idea of {sec} explained.", "tags": ["finance"], "covers": [f"Idea of {sec}"]}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})
    real = httpx.AsyncClient
    monkeypatch.setattr(dg.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        hub.sources.sync("drive")
        hub.engine.serving = {"id": "m", "ready": True}    # pretend a local model is loaded
        yield hub, client, calls


def run_all(hub):
    async def go():
        for _ in range(100):
            if not await hub.digests.step():
                return
    asyncio.run_coroutine_threadsafe(go(), hub.loop).result(60)


def test_digest_drafts_every_section_checks_coverage_and_proposes_per_chapter(env):
    hub, client, calls = env
    vault_before = sorted(p.name for p in hub.vault.root.rglob("*.md"))
    pv = client.get("/api/digest/preview", params={"source": "drive", "path": "finance-book.md"}).json()
    assert pv["chapters"] == 2 and pv["sections"] >= 2
    job = client.post("/api/digest", json={"source": "drive", "path": "finance-book.md"}, headers=H).json()
    assert job["model"] == "m" and job["status"] == "running"
    run_all(hub)
    j = client.get(f"/api/digest/{job['id']}").json()
    assert j["status"] == "done" and j["counts"].get("pending", 0) == 0
    assert all(s["covered"] == s["concepts"] for s in j["sections"] if s["status"] == "drafted")   # follow-up filled gaps
    assert any("aren't covered" in c["messages"][-1]["content"] for c in calls)
    assert all(c["response_format"]["type"] == "json_schema" for c in calls)
    cards = [i for i in hub.inbox.items() if i["source"] == "bookshelf"]
    assert len(cards) == len([c for c in j["chapters"] if c["proposals"]]) == 2             # one card per chapter
    assert {c["status"] for c in j["chapters"]} == {"in inbox"}
    assert sorted(p.name for p in hub.vault.root.rglob("*.md")) == vault_before            # nothing written (I1)
    p = hub.writer.proposal(j["chapters"][0]["proposals"][0])
    ch = p["changes"][0]
    assert ch["folder"].startswith("Books/finance-book/") and ch["source"] == "sources/drive/finance-book.md"
    assert "## Source" in ch["body"] and p["agent"] == "digest:m"


def test_digest_waits_for_the_engine_and_resumes_failed_sections(env, monkeypatch):
    hub, client, calls = env
    hub.engine.serving = None
    job = client.post("/api/digest", json={"source": "drive", "path": "finance-book.md", "model": "m"}, headers=H).json()
    run_all(hub)
    j = client.get(f"/api/digest/{job['id']}").json()
    assert j["counts"] == {"pending": j["sections_total"]} and "waiting for the local engine" in j["error"]
    hub.engine.serving = {"id": "m", "ready": True}

    real = hub.digests.complete

    async def boom(*a, **k):
        raise RuntimeError("model crashed")
    hub.digests.complete = boom
    run_all(hub)
    j = client.get(f"/api/digest/{job['id']}").json()
    assert j["counts"] == {"failed": j["sections_total"]} and "model crashed" in j["sections"][0]["error"]
    hub.digests.complete = real
    client.post(f"/api/digest/{job['id']}/resume", headers=H)
    run_all(hub)
    j = client.get(f"/api/digest/{job['id']}").json()
    assert j["counts"].get("failed", 0) == 0 and j["status"] == "done"


def test_digest_routes_need_the_header(env):
    hub, client, calls = env
    assert client.post("/api/digest", json={"source": "drive", "path": "finance-book.md"}).status_code == 403
    assert client.post("/api/digest", json={"source": "drive", "path": "nope.md"}, headers=H).status_code == 404
