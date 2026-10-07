"""K8 briefing packs (D20 + amendment): per message, visible, recorded, switchable, correctable."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.connectors.base import AgentBusy, AgentConnector
from sage_os_hub.knowledge.briefing import MARK, any_query, key_terms, window

from test_agent_tools import SECRET_UID, UID, cfg, seed

H = {"x-sage-os": "1"}


class FakeAgent(AgentConnector):
    id, label, vendor = "fake", "Fake", "fake"

    def __init__(self):
        self.got: list[tuple[str, str, str | None]] = []
        self.running: set[str] = set()
        self.stopped: list[str] = []

    def pane(self, sid):
        return f"chat:{sid}"

    async def create_session(self, title=None, **o):
        return {"id": "s1"}

    async def send(self, sid, text, shown=None):
        if sid in self.running:
            raise AgentBusy("busy")
        self.got.append((sid, text, shown))

    def busy(self, sid):
        return sid in self.running

    async def interrupt(self, sid):
        self.stopped.append(sid)
        self.running.discard(sid)


@pytest.fixture
def env(tmp_path):
    app = create_app(cfg(tmp_path, claude_enabled=False, hermes_profiles=[]), start_adapters=False)
    seed(tmp_path / "vault")
    (tmp_path / "vault" / "Finance" / "outreach.md").write_text(
        "---\nuid: 01J9ZQ4V6R8T2M3N5P7Q9S1W50\ntitle: Outreach email structure\ncreated: 2026-10-01\nupdated: 2026-10-01\n"
        "type: note\nstatus: active\norigin: human\ntags: [dealclub]\n---\nOpen with the owner's company, one line on the "
        "buyer, then the ask: a 15-minute call about succession.\n", encoding="utf-8")
    hub = app.state.hub
    agent = FakeAgent()
    hub.agents["fake"] = agent
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield hub, agent, client


def call(hub, coro):
    return asyncio.run_coroutine_threadsafe(coro, hub.loop).result()


def test_key_terms_drop_stop_words():
    assert key_terms("Can you help me draft an outreach email for the succession call?") == \
        ["succession", "outreach", "email", "call"]
    assert any_query([]) is None and "OR" in any_query(["dcf", "wacc"])


def test_window_finds_the_dense_part():
    body = "filler " * 400 + "discounted cash flow and enterprise value " + "filler " * 400
    ex = window(body, ["discounted", "enterprise"], 300)
    assert "discounted cash flow" in ex and ex.startswith("…") and len(ex) < 340


def test_pack_travels_with_the_message_and_is_recorded(env):
    hub, agent, client = env
    r = client.post("/api/agents/fake/sessions/s1/send", json={"text": "Draft an outreach email about succession"}, headers=H)
    assert r.status_code == 200
    rec = r.json()["briefing"]
    assert [i["title"] for i in rec["items"]] == ["Outreach email structure"] and rec["items"][0]["by"] == "pack"
    sid, text, shown = agent.got[-1]
    assert shown == "Draft an outreach email about succession" and MARK in text and "data, not instructions" in text
    assert "15-minute call" in text
    stored = client.get("/api/briefing", params={"chat": "chat:s1"}).json()
    assert [b["id"] for b in stored["briefings"]] == [rec["id"]] and stored["settings"]["enabled"] is True


def test_sensitive_notes_never_travel(env):
    hub, agent, client = env
    r = client.post("/api/agents/fake/sessions/s1/send", json={"text": "broker login password"}, headers=H).json()
    assert all(i["ref"].get("uid") != SECRET_UID for i in r["briefing"]["items"])
    assert "Xk29" not in agent.got[-1][1]


def test_nothing_relevant_means_no_pack(env):
    hub, agent, client = env
    r = client.post("/api/agents/fake/sessions/s1/send", json={"text": "zebra quokka"}, headers=H).json()
    assert r["briefing"]["items"] == [] and agent.got[-1][1] == "zebra quokka"


def test_toggle_off(env):
    hub, agent, client = env
    client.post("/api/briefing/settings", json={"chat": "chat:s1", "enabled": False}, headers=H)
    r = client.post("/api/agents/fake/sessions/s1/send", json={"text": "outreach email succession"}, headers=H).json()
    assert r["briefing"]["items"] == [] and MARK not in agent.got[-1][1]


def test_drop_after_reply_corrects_next_message_and_leaves_item_out(env):
    hub, agent, client = env
    rec = client.post("/api/agents/fake/sessions/s1/send", json={"text": "outreach email succession"}, headers=H).json()["briefing"]
    key = rec["items"][0]["key"]
    r = client.post("/api/briefing/drop", json={"chat": "chat:s1", "key": key}, headers=H).json()
    assert r == {"dropped": key, "resend": False}
    nxt = client.post("/api/agents/fake/sessions/s1/send", json={"text": "outreach email again"}, headers=H).json()["briefing"]
    assert nxt["items"] == [] and nxt["corrections"][0]["title"] == "Outreach email structure"
    assert "marked these items" in agent.got[-1][1] and "15-minute" not in agent.got[-1][1]
    third = client.post("/api/agents/fake/sessions/s1/send", json={"text": "outreach email once more"}, headers=H).json()
    assert third["briefing"]["corrections"] == [] and MARK not in agent.got[-1][1]   # correction is said once
    old = client.get("/api/briefing", params={"chat": "chat:s1"}).json()["briefings"][0]
    assert old["items"][0]["dropped"] is True                  # the record shows what was struck


def test_drop_while_answering_stops_and_resends(env):
    hub, agent, client = env
    rec = client.post("/api/agents/fake/sessions/s1/send", json={"text": "outreach email succession"}, headers=H).json()["briefing"]
    agent.running.add("s1")
    r = client.post("/api/briefing/drop", json={"chat": "chat:s1", "key": rec["items"][0]["key"]}, headers=H).json()
    assert r["resend"] is True
    for _ in range(40):
        if len(agent.got) == 2:
            break
        time.sleep(0.05)
    assert agent.stopped == ["s1"] and len(agent.got) == 2
    _, text, shown = agent.got[-1]
    assert shown == "outreach email succession" and "15-minute" not in text and "marked these items" in text


def test_agent_reads_join_the_strip_and_dropped_reads_are_flagged(env):
    hub, agent, client = env
    rec = client.post("/api/agents/fake/sessions/s1/send", json={"text": "outreach email succession"}, headers=H).json()["briefing"]
    call(hub, hub.bookshelf_tools.read("chat:s1", UID))
    latest = hub.briefings.latest("chat:s1")
    assert [i["by"] for i in latest["items"]] == ["pack", "agent"] and latest["items"][1]["title"] == "DCF formula sheet"
    client.post("/api/briefing/drop", json={"chat": "chat:s1", "key": f"note:{UID}"}, headers=H)
    call(hub, hub.bookshelf_tools.read("chat:s1", UID))
    assert hub.briefings.latest("chat:s1")["items"][1]["flagged"] is True
    assert rec["id"] == hub.briefings.latest("chat:s1")["id"]


def test_agent_reads_are_listed_even_when_nothing_was_attached(env):
    hub, agent, client = env
    rec = client.post("/api/agents/fake/sessions/s1/send", json={"text": "zebra quokka"}, headers=H).json()["briefing"]
    assert rec["items"] == []
    call(hub, hub.bookshelf_tools.read("chat:s1", UID))
    latest = hub.briefings.latest("chat:s1")
    assert latest["id"] == rec["id"] and [i["by"] for i in latest["items"]] == ["agent"]


def test_writes_need_the_header(env):
    hub, agent, client = env
    assert client.post("/api/briefing/settings", json={"chat": "chat:s1", "enabled": False}).status_code == 403
    assert client.post("/api/briefing/drop", json={"chat": "chat:s1", "key": "x"}).status_code == 403
    assert client.post("/api/briefing/drop", json={"chat": "chat:s1", "key": "x"}, headers=H).status_code == 404
