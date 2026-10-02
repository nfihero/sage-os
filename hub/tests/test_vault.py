"""Bookshelf K1: the vault is read, validated against the contract, and served read-only."""
from fastapi.testclient import TestClient

from sage_os_hub import app as app_module
from sage_os_hub.adapters.vault import VaultAdapter
from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.knowledge import SearchIndex, Vault
from sage_os_hub.knowledge.vault import parse_note

A = "01J9ZQ4V6R8T2M3N5P7Q9S1W3Y"
B = "01J9ZQ4V6R8T2M3N5P7Q9S1W40"


def note(uid=A, title="DCF formula sheet", origin="human", extra="", body="# DCF\n\nValue = sum of discounted cash flows.\n"):
    return (f"---\nuid: {uid}\ntitle: {title}\ncreated: 2026-09-30\nupdated: 2026-09-30T10:00:00\n"
            f"type: reference\nstatus: active\norigin: {origin}\n{extra}---\n{body}")


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_ensure_creates_only_folders(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    assert sorted(p.name for p in v.root.iterdir()) == ["Archive", "Attachments"]
    assert v.summary()["count"] == 0


def test_valid_note_and_links_resolve_by_uid(tmp_path):
    v = Vault(tmp_path)
    write(tmp_path, "Finance/dcf-formula-sheet.md", note(extra=f"tags: [finance, valuation]\nlinks: [{B}, 01J9ZQ4V6R8T2M3N5P7Q9S1W41]\n"))
    write(tmp_path, "Finance/wacc.md", note(uid=B, title="WACC"))
    rows = {r["path"]: r for r in v.summary()["notes"]}
    dcf = rows["Finance/dcf-formula-sheet.md"]
    assert dcf["problems"] == [] and dcf["ref"] == A and dcf["folder"] == "Finance"
    assert dcf["created"] == "2026-09-30" and dcf["tags"] == ["finance", "valuation"]
    assert dcf["links"] == [{"uid": B, "title": "WACC"}, {"uid": "01J9ZQ4V6R8T2M3N5P7Q9S1W41", "title": None}]
    full = v.read(A)
    assert full["body"].startswith("# DCF") and full["source"].startswith("---") and full["frontmatter"]["type"] == "reference"


def test_contract_problems_are_named_not_hidden(tmp_path):
    cases = {
        "plain.md": ("# Just text\n", "no frontmatter"),
        "broken.md": ("---\ntitle: [unclosed\n---\nbody\n", "not valid YAML"),
        "empty-block.md": ("---\n---\nbody\n", "missing uid"),
        "bad-uid.md": (note(uid="not-a-ulid"), "not a ULID"),
        "bad-origin.md": (note(origin="robot"), "origin must be one of"),
        "agent-no-id.md": (note(origin="agent"), "needs an `agent` id"),
        "abs-front.md": (note(extra="source: C:\\Users\\you\\secret.pdf\n"), "absolute path in frontmatter"),
        "abs-link.md": (note(body="see [file](/home/x/notes.md)\n"), "absolute path in a link"),
        "Not A Slug.md": (note(), "isn't a slug"),
    }
    for i, (name, (text, _)) in enumerate(cases.items()):
        text = text.replace(A, f"01J9ZQ4V6R8T2M3N5P7Q9S1X{i:02d}")     # keep uids unique
        write(tmp_path, name, text)
    rows = {r["path"]: r for r in Vault(tmp_path).summary()["notes"]}
    for name, (_, expected) in cases.items():
        assert any(expected in p for p in rows[name]["problems"]), (name, rows[name]["problems"])
    assert rows["plain.md"]["title"] == "Just text"          # still listed, titled from the heading


def test_agent_note_with_id_is_valid(tmp_path):
    n, _, _ = parse_note("Inbox/finding.md", note(origin="agent", extra="agent: hermes:default:api_123\n"))
    assert n.problems == [] and n.agent == "hermes:default:api_123"


def test_duplicate_uids_fall_back_to_path_refs(tmp_path):
    write(tmp_path, "a.md", note())
    write(tmp_path, "b.md", note())
    rows = Vault(tmp_path).summary()["notes"]
    assert all(any("duplicate uid" in p for p in r["problems"]) for r in rows)
    assert {r["ref"] for r in rows} == {"a.md", "b.md"}


def test_hidden_attachments_and_archive(tmp_path):
    write(tmp_path, ".obsidian/workspace.md", "x")
    write(tmp_path, "Attachments/scan.md", "x")
    write(tmp_path, "Archive/old-note.md", note())
    rows = Vault(tmp_path).summary()["notes"]
    assert [(r["path"], r["archived"]) for r in rows] == [("Archive/old-note.md", True)]


def test_read_refuses_unknown_refs_and_paths_outside(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    (tmp_path / "outside.md").write_text(note(), encoding="utf-8")
    assert v.read("../outside.md") is None and v.read(A) is None


def test_cache_picks_up_edits(tmp_path):
    v = Vault(tmp_path)
    write(tmp_path, "n.md", note(title="One"))
    assert v.summary()["notes"][0]["title"] == "One"
    write(tmp_path, "n.md", note(title="Two, a longer title"))
    assert v.summary()["notes"][0]["title"] == "Two, a longer title"


def test_adapter_publishes_only_on_change(tmp_path):
    class Rec:
        def __init__(self):
            self.panels, self.events = [], []

        def panel(self, name, data, *, broadcast=True):
            self.panels.append(data)

        def event(self, kind, source, type_, data, *, persist=True, ts=None):
            self.events.append(type_)
    rec, v = Rec(), Vault(tmp_path / "vault")
    v.ensure()
    a = VaultAdapter(rec, v, SearchIndex(tmp_path / "index.db"), 5)
    a.poll(); a.poll()
    write(tmp_path / "vault", "n.md", note())
    a.poll()
    assert rec.panels[-1]["indexed"] == 1 and len(rec.panels) == 2 and rec.events == ["vault.changed"]


def test_routes(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(app_module, "open_folder", opened.append)
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db", vault_journal=tmp_path / "journal.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db",
                 claude_workspaces=[str(tmp_path)], claude_enabled=False, hermes_profiles=[])
    app = create_app(cfg, start_adapters=False)
    write(tmp_path / "vault", "Finance/dcf.md", note())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/vault").json()["count"] == 1
        assert c.get("/api/vault/note", params={"ref": A}).json()["title"] == "DCF formula sheet"
        assert c.get("/api/vault/note", params={"ref": "nope"}).status_code == 404
        assert c.post("/api/vault/open").status_code == 403                 # write guard
        r = c.post("/api/vault/open", headers={"x-sage-os": "1"})
        assert r.status_code == 200 and opened == [tmp_path / "vault"]
