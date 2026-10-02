"""Bookshelf K4: secret screening before anything is stored (BookShelf I4).

Sample secrets are assembled at runtime so no token-shaped string sits in the repo (GitHub push
protection would rightly complain).
"""
import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.knowledge import SearchIndex, SensitiveContent, Vault, Writer, screen
from sage_os_hub.knowledge.screen import BANK, CARD, CREDENTIAL, GOV_ID

AGENT = "claude:cs_test"
CANARY = "sk-" + "ant-" + "api03-" + "CANARY" + "Q7x" * 12          # unique, findable on disk


def j(*parts):
    return "".join(parts)


POSITIVE = {
    CREDENTIAL: [
        CANARY,
        j("-----BEGIN ", "OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEA\n-----END OPENSSH PRIVATE KEY-----"),
        j("AK", "IA", "Z" * 16), j("gh", "p_", "a1B2" * 9), j("github_", "pat_", "x" * 30),
        j("sk-", "proj-", "A" * 40), j("xo", "xb-", "1234567890-abcdef"), j("AI", "za", "S" * 35),
        j("sk_", "live_", "4eC39HqLyjWDarjtT1zdp7dc"), j("ey", "JhbGciOiJIUzI1NiJ9.", "ey", "JzdWIiOiIxMjM0NTY3ODkwIn0.", "dozjgNryP4J3jVmNHl0w5N"),
        "postgres://admin:hunter2pass@db.internal:5432/app", "password: Tr0ub4dor&3", "My API key = 9f8e7d6c5b4a3210",
        j("API_SERVER", "_KEY=", "f3c9a1b2d4e5f6a7"),
    ],
    CARD: ["card 4111 1111 1111 1111 exp 12/28", "5500-0000-0000-0004", "card 4111 1111 1111 1111.", "4111111111111111"],
    GOV_ID: ["SSN 123-45-6789", "Aadhaar 2341 2341 2346"],
    BANK: ["IBAN GB82 WEST 1234 5698 7654 32"],
}
NEGATIVE = [
    "Enterprise value is the sum of discounted free cash flows.", "password: <your password>",
    "password: ********", "api_key = os.getenv('ANTHROPIC_API_KEY')", "primary_key = id_column",
    "password = input('Password: ')", "Call me on +1 415 555 0132 on 2026-10-01.", "ISBN 978-0-13-468599-1",
    "order 4111 1111 1111 1112", "ref 2341 2341 2345", "I use sk-learn and scikit-image.",
    "See https://example.com/a:b and git@github.com:nfihero/sage-os.git", "The secret to DCF is the terminal value.",
    "Set API_SERVER_KEY in the .env file.", "Use 1Password: password: see vault",
    # spreadsheet decimals (regression, 1 Oct): fraction digits passed the card/Aadhaar checksums
    "99.9999999999999", "1234.4111111111111111", "4111111111111111.5", "0,4111111111111111", "x 1.234123412346 y",
]


@pytest.mark.parametrize("category,text", [(c, t) for c, ts in POSITIVE.items() for t in ts])
def test_catches(category, text):
    assert screen(text) == category


@pytest.mark.parametrize("text", NEGATIVE)
def test_leaves_ordinary_text_alone(text):
    assert screen(text) is None


def everything_on_disk(root):
    return b"".join(p.read_bytes() for p in root.rglob("*") if p.is_file())


@pytest.fixture
def w(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    return Writer(v, tmp_path / "journal.db")


@pytest.mark.parametrize("change,where", [
    ({"op": "create", "folder": "Inbox", "title": "Keys", "body": f"my key {CANARY}"}, "change 1 (body)"),
    ({"op": "create", "folder": "Inbox", "title": f"key {CANARY}", "body": "x"}, "change 1 (title)"),
    ({"op": "create", "folder": "Inbox", "title": "t", "body": "x", "tags": [CANARY[:60]]}, "change 1 (tags)"),
])
def test_proposal_refused_and_nothing_stored(w, tmp_path, change, where):
    with pytest.raises(SensitiveContent) as exc:
        w.propose(AGENT, "notes", [change])
    assert exc.value.where == where and exc.value.category == CREDENTIAL
    assert CANARY not in str(exc.value) and CANARY[:20] not in str(exc.value)     # never echoed
    assert w.proposals() == []
    w.close()
    assert CANARY[:30].encode() not in everything_on_disk(tmp_path)              # canary: nowhere on disk


def test_summary_is_screened_too(w):
    with pytest.raises(SensitiveContent, match="the summary"):
        w.propose(AGENT, f"use {CANARY}", [{"op": "create", "folder": "Inbox", "title": "t", "body": "x"}])


def test_users_own_secret_note_is_kept_out_of_search(tmp_path):
    v = Vault(tmp_path / "vault")
    v.ensure()
    (v.root / "Inbox").mkdir()
    (v.root / "Inbox" / "wifi.md").write_text(
        "---\nuid: 01J9ZQ4V6R8T2M3N5P7Q9S1W3Y\ntitle: Router setup\ncreated: 2026-10-01\nupdated: 2026-10-01\n"
        f"type: note\nstatus: active\norigin: human\n---\nThe admin login is password: Xk29fjq0LmP and {CANARY}\n", encoding="utf-8")
    note = v.scan()[0]
    assert note.sensitive == CREDENTIAL and note.problems == []                   # flagged, not a contract problem
    idx = SearchIndex(tmp_path / "index.db")
    idx.sync(v.scan(), v.read_body)
    assert idx.search("admin login")["results"] == []                            # body not indexed
    assert [r["title"] for r in idx.search("router")["results"]] == ["Router setup"]
    idx.close()
    assert CANARY[:30].encode() not in (tmp_path / "index.db").read_bytes()
    w = Writer(v, tmp_path / "journal.db")                                       # an agent may still retag it:
    p = w.propose(AGENT, "", [{"op": "update", "uid": "01J9ZQ4V6R8T2M3N5P7Q9S1W3Y", "tags": ["network"]}])
    assert p["status"] == "pending"                                              # only the agent's text is screened


H = {"x-sage-os": "1"}


def hub_cfg(tmp_path):
    return Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db",
                  vault_journal=tmp_path / "journal.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db", claude_workspaces=[str(tmp_path)], claude_enabled=False, hermes_profiles=[])


def secret_proposal(title="Router"):
    return {"agent": AGENT, "summary": "wifi notes",
            "changes": [{"op": "create", "folder": "Inbox", "title": title, "body": f"token {CANARY}"}]}


def held(c):
    return [i for i in c.get("/api/state").json()["panels"]["inbox"] if i["context"].get("held")]


def test_route_holds_in_memory_and_logs_without_content(tmp_path):
    with TestClient(create_app(hub_cfg(tmp_path), start_adapters=False), base_url="http://127.0.0.1") as c:
        r = c.post("/api/vault/proposals", headers=H, json=secret_proposal())
        assert r.status_code == 202 and r.json()["status"] == "held" and "a password or key" in r.text
        assert CANARY[:20] not in r.text                                          # never echoed to the agent
        (card,) = held(c)
        assert card["choices"] == ["reject", "save_anyway"] and card["context"]["where"] == "change 1 (body)"
        assert CANARY[:20] not in card["title"] + card["detail"]                  # hidden unless "Show content"
        events = c.get("/api/state").json()["events"]
        (ev,) = [e for e in events if e["type"] == "proposal.screened"]
        assert ev["data"] == {"agent": AGENT, "where": "change 1 (body)", "category": CREDENTIAL}
        assert c.get("/api/vault/proposals").json() == []                        # not in the journal
        assert CANARY[:30].encode() not in everything_on_disk(tmp_path)          # held = memory only
        c.post(f"/api/inbox/{card['id']}", json={"choice": "reject"}, headers=H)
        assert held(c) == [] and c.get("/api/vault/proposals").json() == []
    assert CANARY[:30].encode() not in everything_on_disk(tmp_path)              # hub.db, journal, vault, index


def test_save_anyway_files_it_and_records_only_the_category(tmp_path):
    with TestClient(create_app(hub_cfg(tmp_path), start_adapters=False), base_url="http://127.0.0.1") as c:
        c.post("/api/vault/proposals", headers=H, json=secret_proposal())
        (card,) = held(c)
        assert c.post(f"/api/inbox/{card['id']}", json={"choice": "save_anyway", "note": "my router"}, headers=H).status_code == 200
        (p,) = c.get("/api/vault/proposals").json()
        assert p["status"] == "applied" and p["screened"] == CREDENTIAL
        note = tmp_path / "vault" / "Inbox" / "router.md"
        assert CANARY in note.read_text(encoding="utf-8")                        # the user's explicit choice
        events = c.get("/api/state").json()["events"]
        assert any(e["type"] == "proposal.override" for e in events)
        assert CANARY[:20] not in str(events)                                     # logs: category, never content
        assert c.get("/api/vault/search", params={"q": "token"}).json()["results"] == []   # body still out of search
        (batch,) = c.get("/api/vault/history").json()
        c.post(f"/api/vault/batches/{batch['id']}/undo", headers=H)
        assert not note.exists()                                                  # and undo works as usual


def test_agents_cannot_override(w):
    p = w.propose(AGENT, "", [{"op": "create", "folder": "Inbox", "title": "ok", "body": "fine"}])
    assert p["screened"] is None                                                  # normal proposals record no override
    import inspect
    from sage_os_hub import app as app_module
    src = inspect.getsource(app_module)
    assert src.count("override=") == 1 and "def hold_screened" in src             # only the held card's resolver
