"""Bookshelf K5: agents read and propose through MCP -- in-process for Claude, Streamable HTTP for others."""
import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.connectors.claude import BOOKSHELF_TOOLS, bookshelf_sdk_tools

UID = "01J9ZQ4V6R8T2M3N5P7Q9S1W3Y"
SECRET_UID = "01J9ZQ4V6R8T2M3N5P7Q9S1W40"
H = {"x-sage-os": "1"}


def seed(vault):
    (vault / "Finance").mkdir(parents=True, exist_ok=True)
    (vault / "Finance" / "dcf-formula-sheet.md").write_text(
        f"---\nuid: {UID}\ntitle: DCF formula sheet\ncreated: 2026-03-14\nupdated: 2026-03-14\ntype: reference\n"
        "status: active\norigin: human\nsource: sources/drive/Finance/dcf.pdf\ntags: [finance]\n---\nEnterprise value is the sum of discounted free cash flows.\n",
        encoding="utf-8")
    (vault / "Finance" / "broker-login.md").write_text(
        f"---\nuid: {SECRET_UID}\ntitle: Broker login\ncreated: 2026-03-14\nupdated: 2026-03-14\ntype: note\n"
        "status: active\norigin: human\n---\npassword: Xk29fjq0LmP\n", encoding="utf-8")


def cfg(tmp_path, port=8787, **kw):
    return Config(data_dir=tmp_path / "data", hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db",
                  vault_journal=tmp_path / "journal.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db", claude_workspaces=[str(tmp_path)], port=port, **kw)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def hub(tmp_path):
    app = create_app(cfg(tmp_path, claude_enabled=False, hermes_profiles=[]), start_adapters=False)
    seed(tmp_path / "vault")
    with TestClient(app, base_url="http://127.0.0.1"):
        yield app.state.hub


def test_search_and_read(hub):
    t = hub.bookshelf_tools
    res = asyncio.run_coroutine_threadsafe(t.search("hermes:default", "discounted cash"), hub.loop).result()
    assert [r["title"] for r in res["results"]] == ["DCF formula sheet"] and "«" in res["results"][0]["snippet"]
    note = asyncio.run_coroutine_threadsafe(t.read("hermes:default", UID), hub.loop).result()
    assert note["body"].startswith("Enterprise value") and note["origin"] == "human"
    assert note["source"] == "sources/drive/Finance/dcf.pdf"     # the citation, so the agent can follow it (review 3 Oct)
    full = hub.vault.read(UID)
    assert full["source"] == "sources/drive/Finance/dcf.pdf" and full["text"].startswith("---")
    assert "error" in asyncio.run_coroutine_threadsafe(t.read("x", "01J9ZQ4V6R8T2M3N5P7Q9S1W99"), hub.loop).result()


def test_sensitive_note_text_is_withheld(hub):
    t = hub.bookshelf_tools
    note = asyncio.run_coroutine_threadsafe(t.read("claude:cs_x", SECRET_UID), hub.loop).result()
    assert note["body"] is None and "isn't shared" in note["withheld"] and "Xk29" not in json.dumps(note)
    found = asyncio.run_coroutine_threadsafe(t.search("claude:cs_x", "Xk29fjq0LmP"), hub.loop).result()
    assert found["results"] == []


def test_propose_list_and_provenance(hub):
    t = hub.bookshelf_tools
    vault_before = sorted(p.name for p in hub.vault.root.rglob("*.md"))
    r = asyncio.run_coroutine_threadsafe(t.propose("hermes:default", [
        {"op": "create", "folder": "Finance", "title": "WACC", "body": "Weighted cost of capital."}], "add WACC"), hub.loop).result()
    assert r["status"] == "pending" and sorted(p.name for p in hub.vault.root.rglob("*.md")) == vault_before
    (card,) = [i for i in hub.inbox.items() if i["source"] == "bookshelf"]
    assert card["context"]["agent"] == "hermes:default"
    mine = asyncio.run_coroutine_threadsafe(t.proposals("hermes:default"), hub.loop).result()["proposals"]
    assert [p["proposal_id"] for p in mine] == [r["proposal_id"]]
    assert asyncio.run_coroutine_threadsafe(t.proposals("claude:cs_other"), hub.loop).result()["proposals"] == []
    bad = asyncio.run_coroutine_threadsafe(t.propose("hermes:default", [{"op": "delete", "uid": UID}]), hub.loop).result()
    assert bad["status"] == "refused" and "op must be" in bad["error"]
    held = asyncio.run_coroutine_threadsafe(t.propose("hermes:default", [
        {"op": "create", "folder": "Inbox", "title": "t", "body": "password: Tr0ub4dor&3x"}]), hub.loop).result()
    assert held["status"] == "held" and "Tr0ub4dor" not in json.dumps(held)


def test_claude_sdk_tools_carry_the_session_id(hub):
    tools = {t.name: t for t in bookshelf_sdk_tools(hub.bookshelf_tools, "claude:cs_abc")}
    assert set(f"mcp__bookshelf__{n}" for n in tools) == set(BOOKSHELF_TOOLS)
    call = lambda name, args: asyncio.run_coroutine_threadsafe(tools[name].handler(args), hub.loop).result()
    found = json.loads(call("search_notes", {"query": "dcf"})["content"][0]["text"])
    assert found["results"][0]["uid"] == UID
    out = json.loads(call("propose_note", {"changes": [{"op": "update", "uid": UID, "tags": ["finance", "dcf"]}],
                                           "summary": "tag it"})["content"][0]["text"])
    assert out["status"] == "pending"
    assert hub.writer.proposal(out["proposal_id"])["agent"] == "claude:cs_abc"   # set by Sage OS, not the model


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live(tmp_path):
    """A real hub on a free port with a Hermes connector, so the MCP endpoint speaks HTTP."""
    port = free_port()
    app = create_app(cfg(tmp_path, port=port, claude_enabled=False, hermes_profiles=["default"]), start_adapters=False)
    seed(tmp_path / "vault")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield app.state.hub, f"http://127.0.0.1:{port}"
    server.should_exit = True
    th.join(5)


def test_hermes_endpoint_end_to_end(live):
    hub, base = live

    async def go():
        async with streamable_http_client(f"{base}/mcp/hermes/default/") as (read, write, *_):
            async with ClientSession(read, write) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                assert names == {"search_notes", "read_note", "propose_note", "list_proposals", "search_sources", "read_source"}
                found = json.loads((await s.call_tool("search_notes", {"query": "enterprise value"})).content[0].text)
                note = json.loads((await s.call_tool("read_note", {"uid": found["results"][0]["uid"]})).content[0].text)
                prop = json.loads((await s.call_tool("propose_note", {"changes": [
                    {"op": "create", "folder": "Finance", "title": "From Hermes", "body": "hello"}]})).content[0].text)
                return note, prop
    note, prop = run(go())
    assert note["title"] == "DCF formula sheet" and prop["status"] == "pending"
    assert hub.writer.proposal(prop["proposal_id"])["agent"] == "hermes:default"     # from the URL path
    assert not (hub.vault.root / "Finance" / "from-hermes.md").exists()               # only a proposal


def test_endpoint_refuses_foreign_origin_and_host(live):
    _, base = live
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    hdr = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    r = httpx.post(f"{base}/mcp/hermes/default/", json=body, headers=hdr | {"origin": "https://evil.example"})
    assert r.status_code in (400, 403)
    r = httpx.post(f"{base}/mcp/hermes/default/", json=body, headers=hdr | {"host": "evil.example"})
    assert r.status_code in (400, 403, 421)
    assert httpx.post(f"{base}/mcp/hermes/nobody/", json=body, headers=hdr).status_code in (404, 405)
