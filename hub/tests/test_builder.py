"""K6: notes start from whatever the user provided -- starter notes from a source, then agent drafts."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.connectors.base import AgentConnector
from sage_os_hub.knowledge import ProposalError, Vault, Writer
from sage_os_hub.knowledge.proposals import IMPORTER

from test_sources import office, tiny_pdf

H = {"x-sage-os": "1"}


@pytest.fixture
def drive(tmp_path):
    g = tmp_path / "G"
    files = {
        "My Drive/Finance/FIN 101/Lecture9_CostofCapital.pptx": office({
            "ppt/slides/slide1.xml": "<p:sld><a:p><a:t>Cost of Capital</a:t></a:p></p:sld>",
            "ppt/slides/slide2.xml": "<p:sld><a:p><a:t>Weighted average cost of capital</a:t></a:p><a:p><a:t>WACC = E/V Re + D/V Rd</a:t></a:p></p:sld>"}),
        "My Drive/Finance/FIN 101/Lecture10_Leverage.pdf": tiny_pdf("Capital structure and leverage with WACC"),
        "My Drive/Finance/FIN 101/QuestionBank.pdf": tiny_pdf("Compute WACC and capital budgeting questions"),
        "My Drive/Finance/FIN 101/class-notes.md": b"# FIN 101 notes\n\nNPV beats IRR when projects differ in scale.\n",
        "My Drive/Finance/syllabus.pdf": tiny_pdf("Course syllabus for finance"),
        "Other computers/Mac/Projects/Unit-5/src/Main.java": b"class Main { /* bond pricing */ }\n",
        "Other computers/Mac/Projects/Unit-5/src/Bond.java": b"class Bond { /* coupon */ }\n",
        "Other computers/Mac/Notes/journal.md": b"---\ntitle: My journal\ntags: [daily]\n---\nToday I learned about duration.\n",
    }
    for rel, data in files.items():
        p = g / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return g


def make(tmp_path, drive, **kw):
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "i.db",
                 vault_journal=tmp_path / "j.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db",
                 claude_workspaces=[str(tmp_path)], claude_enabled=False, hermes_profiles=[],
                 sources=[{"name": "drive", "path": str(drive), "include": ["My Drive", "Other computers/Mac"],
                           "notes_folder": "Drive", "strip": ["My Drive", "Other computers"]}], **kw)
    app = create_app(cfg, start_adapters=False)
    app.state.hub.sources.sync("drive")
    return app


def run(hub, coro):
    return asyncio.run_coroutine_threadsafe(coro, hub.loop).result()


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_collections_roll_up_and_map_into_the_vault(tmp_path, drive):
    hub = make(tmp_path, drive).state.hub
    cols = {c.dir: c for c in hub.builder.collections("drive")}
    assert set(cols) == {"My Drive/Finance/FIN 101", ""}                     # small folders roll up to the root
    assert sorted(cols["My Drive/Finance/FIN 101"].docs)[0].endswith("Lecture10_Leverage.pdf")
    assert cols["My Drive/Finance/FIN 101"].markdown == ["My Drive/Finance/FIN 101/class-notes.md"]
    assert "Other computers/Mac/Projects/Unit-5/src/Main.java" in cols[""].docs
    spec = hub.sources.specs["drive"]
    assert hub.builder.vault_folder(spec, "My Drive/Finance/FIN 101") == "Drive/Finance/FIN 101"
    assert hub.builder.vault_folder(spec, "Other computers/Mac/Notes") == "Drive/Mac/Notes"
    assert hub.builder.vault_folder(spec, "") == "Drive"


def test_starter_notes_are_proposed_never_written(tmp_path, drive):
    app = make(tmp_path, drive)
    hub = app.state.hub
    with TestClient(app, base_url="http://127.0.0.1") as c:
        before = snapshot(tmp_path / "vault")
        r = c.post("/api/sources/drive/build", headers=H).json()
        assert r["proposed"] == 2 and r["notes"] == 4 and r["left_out"] == []        # 2 areas: Drive, Drive/Finance/FIN 101
        assert snapshot(tmp_path / "vault") == before                                    # I1: nothing until approved
        cards = [i for i in c.get("/api/state").json()["panels"]["inbox"] if i["source"] == "bookshelf"]
        assert len(cards) == 2 and all(i["context"]["agent"] == IMPORTER for i in cards)
        assert c.post("/api/sources/drive/build", headers=H).json()["proposed"] == 0     # pending: no duplicates
        statuses = {x["dir"]: x["status"] for x in c.get("/api/sources/drive/collections").json()}
        assert statuses == {"My Drive/Finance/FIN 101": "pending", "": "pending"}
        fin = next(i for i in cards if "FIN 101" in i["title"] or "FIN 101" in i["detail"])
        assert c.post(f"/api/inbox/{fin['id']}", json={"choice": "approve"}, headers=H).status_code == 200
        check_built(c, hub)


def check_built(c, hub):
    notes = {n.path: n for n in hub.vault.scan()}
    col = notes["Drive/Finance/FIN 101/fin-101.md"]
    assert col.type == "collection" and col.origin == "agent" and col.agent == IMPORTER and col.problems == []
    body = hub.vault.read(col.ref)["body"]
    assert "Lecture9_CostofCapital.pptx** · slides: Cost of Capital; Weighted average cost of capital" in body
    assert "`sources/drive/My Drive/Finance/FIN 101/QuestionBank.pdf`" in body and "wacc" in body.lower()
    imported = notes["Drive/Finance/FIN 101/fin-101-notes.md"]
    assert imported.origin == "imported" and imported.source == "sources/drive/My Drive/Finance/FIN 101/class-notes.md"
    assert hub.vault.read(imported.ref)["body"] == "# FIN 101 notes\n\nNPV beats IRR when projects differ in scale.\n"   # verbatim
    assert {x["dir"]: x["status"] for x in c.get("/api/sources/drive/collections").json()}["My Drive/Finance/FIN 101"] == "built"
    assert c.post("/api/sources/drive/build", headers=H).json()["proposed"] == 0         # built or pending: idempotent


def test_markdown_frontmatter_title_and_tags_carry_over(tmp_path, drive):
    hub = make(tmp_path, drive).state.hub
    plan = hub.builder.starter_plan("drive")
    md = next(ch for p in plan["proposals"] for ch in p["changes"] if ch.get("source", "").endswith("journal.md"))
    assert md["title"] == "My journal" and md["tags"] == ["daily"] and md["folder"] == "Drive/Mac/Notes"
    assert md["body"] == "Today I learned about duration.\n"


def test_only_the_importer_may_mark_notes_imported(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    w = Writer(v, tmp_path / "j.db")
    ch = {"op": "create", "folder": "Inbox", "title": "Mine", "body": "x", "origin": "imported", "source": "sources/a/b.md"}
    by_agent = w.approve(w.propose("hermes:default", "", [ch])["id"])
    by_importer = w.approve(w.propose(IMPORTER, "", [dict(ch, title="Theirs")])["id"])
    notes = {n.title: n for n in v.scan()}
    assert notes["Mine"].origin == "agent" and notes["Mine"].agent == "hermes:default"   # agents can't claim imported
    assert notes["Theirs"].origin == "imported" and notes["Theirs"].source == "sources/a/b.md"
    with pytest.raises(ProposalError, match="never changes"):
        w.propose("hermes:default", "", [{"op": "update", "uid": notes["Mine"].uid, "origin": "imported"}])
    assert by_agent and by_importer


class FakeAgent(AgentConnector):
    id, label, vendor = "hermes:default", "Hermes", "hermes"

    def __init__(self):
        self.sent = []

    def pane(self, sid):
        return f"fake:{sid}"

    async def create_session(self, title=None, **options):
        return {"id": "api_1", "title": title}

    async def send(self, sid, text):
        self.sent.append((sid, text))


def test_draft_notes_briefs_an_agent_with_the_collection(tmp_path, drive):
    app = make(tmp_path, drive)
    hub = app.state.hub
    fake = FakeAgent()
    hub.agents["hermes:default"] = fake
    with TestClient(app, base_url="http://127.0.0.1") as c:
        r = c.post("/api/sources/drive/draft", json={"folder": "My Drive/Finance/FIN 101"}, headers=H)
        assert r.status_code == 200 and r.json()["agent"] == "hermes:default"
        assert c.post("/api/sources/drive/draft", json={"folder": "nope"}, headers=H).status_code == 404
        assert c.post("/api/sources/drive/draft", json={"folder": "", "agent": "ghost"}, headers=H).status_code == 400
    (sid, prompt), = fake.sent
    assert "read_source" in prompt and "propose_note" in prompt and "My Drive/Finance/FIN 101/QuestionBank.pdf" in prompt
    assert '"folder": "Drive/Finance/FIN 101"' in prompt and "Don't invent facts" in prompt and '"source": "sources/drive/' in prompt


def test_review_fixes(tmp_path, drive):
    """Code review (2 Oct): status covers markdown notes; updates can set a citation; busy agent is 409."""
    from sage_os_hub.connectors.base import AgentBusy
    app = make(tmp_path, drive)
    hub = app.state.hub
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.post("/api/sources/drive/build", headers=H)
        for item in [i for i in c.get("/api/state").json()["panels"]["inbox"] if i["source"] == "bookshelf"]:
            c.post(f"/api/inbox/{item['id']}", json={"choice": "approve"}, headers=H)
        (drive / "My Drive/Finance/FIN 101/later.md").write_text("# Later\n\nAdded after the first build.\n", encoding="utf-8")
        hub.sources.sync("drive")
        statuses = {x["dir"]: x["status"] for x in c.get("/api/sources/drive/collections").json()}
        assert statuses["My Drive/Finance/FIN 101"] == "new"                    # a new markdown file makes it buildable
        r = c.post("/api/sources/drive/build", headers=H).json()
        assert r["proposed"] == 1 and r["notes"] == 1 and r["already"] == 4
        note = next(n for n in hub.vault.scan() if n.title == "WACC" or n.type == "collection")
        p = hub.writer.propose("hermes:default", "", [{"op": "update", "uid": note.uid, "source": "sources/drive/x.pdf"}])
        hub.writer.approve(p["id"])
        assert next(n for n in hub.vault.scan() if n.uid == note.uid).source == "sources/drive/x.pdf"

        class Busy(FakeAgent):
            async def send(self, sid, text):
                raise AgentBusy("still working")
        hub.agents["hermes:default"] = Busy()
        assert c.post("/api/sources/drive/draft", json={"folder": "My Drive/Finance/FIN 101"}, headers=H).status_code == 409


def test_outside_callers_cannot_pose_as_the_importer(tmp_path, drive):
    """vibe-security (2 Oct): the importer may mark notes origin: imported, so its name is reserved."""
    app = make(tmp_path, drive)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        r = c.post("/api/vault/proposals", headers=H, json={"agent": "Sage-OS:importer", "changes": [
            {"op": "create", "folder": "Inbox", "title": "t", "body": "x", "origin": "imported"}]})
        assert r.status_code == 400 and "reserved" in r.text
